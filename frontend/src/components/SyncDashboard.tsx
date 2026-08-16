import React, { useCallback, useEffect, useState } from "react";
import { api, SyncStatus } from "../api/client";
import {
  Card,
  EmptyState,
  ErrorBanner,
  PageHeader,
  Spinner,
  StatCard,
  formatNumber,
} from "./ui";

export function SyncDashboard() {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [meta, setMeta] = useState<any>(null);
  const [running, setRunning] = useState<"full" | "incremental" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const [s, m] = await Promise.all([api.syncStatus(), api.syncMetadata()]);
      setStatus(s);
      setMeta(m);
    } catch {
      /* the shell's health banner already reports an unreachable backend */
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 5000);
    return () => clearInterval(id);
  }, [fetchStatus]);

  const runSync = async (mode: "full" | "incremental") => {
    setRunning(mode);
    setError(null);
    try {
      const result =
        mode === "full" ? await api.fullSync() : await api.incrementalSync();
      setStatus({
        is_running: false,
        progress: 100,
        current_phase: "Complete",
        result,
      });
      await fetchStatus();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunning(null);
    }
  };

  const r = status?.result;
  const busy = running !== null || status?.is_running;

  return (
    <div>
      <PageHeader
        title="Synchronization"
        subtitle="Index Jira issues into the vector database. Incremental sync only reprocesses what changed."
        actions={
          <>
            <button
              onClick={() => runSync("incremental")}
              disabled={busy}
              className="btn-primary"
            >
              {running === "incremental" && <Spinner />}
              Incremental Sync
            </button>
            <button
              onClick={() => runSync("full")}
              disabled={busy}
              className="btn-secondary"
            >
              {running === "full" && <Spinner />}
              Full Rebuild
            </button>
          </>
        }
      />

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      {/* Mode explainer */}
      <div className="mb-6 grid gap-3 md:grid-cols-2">
        <div className="card p-4">
          <p className="text-sm font-semibold text-brand">Incremental Sync</p>
          <p className="mt-1 text-xs leading-relaxed text-content-muted">
            Fetches only issues updated since the last run and skips those whose
            content hash is unchanged. This is the routine operation.
          </p>
        </div>
        <div className="card p-4">
          <p className="text-sm font-semibold text-content">Full Rebuild</p>
          <p className="mt-1 text-xs leading-relaxed text-content-muted">
            Clears the store and re-embeds every issue. Required after changing
            the embedding model, since old vectors are not comparable to new ones.
          </p>
        </div>
      </div>

      {/* Progress */}
      {status?.is_running && (
        <Card className="mb-6">
          <div className="mb-2 flex items-center justify-between">
            <span className="flex items-center gap-2 text-sm text-content">
              <Spinner className="text-brand" />
              {status.current_phase || "Working…"}
            </span>
            <span className="font-mono text-sm tabular-nums text-content-muted">
              {status.progress}%
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-edge-strong">
            <div
              className="h-full rounded-full bg-brand transition-[width] duration-500"
              style={{ width: `${status.progress}%` }}
            />
          </div>
        </Card>
      )}

      {/* Results */}
      {r ? (
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
          <StatCard label="New" value={r.new_issues} tone="ok" />
          <StatCard label="Updated" value={r.updated_issues} tone="brand" />
          <StatCard label="Deleted" value={r.deleted_issues} />
          <StatCard
            label="Skipped"
            value={r.skipped_issues}
            hint="unchanged"
          />
          <StatCard label="Embeddings" value={formatNumber(r.total_embeddings)} />
          <StatCard
            label="Tokens Saved"
            value={formatNumber(r.total_tokens_saved)}
            tone="ok"
            hint="re-embedding avoided"
          />
        </div>
      ) : (
        !status?.is_running && (
          <Card className="mb-6">
            <EmptyState
              icon="⟳"
              title="No sync run yet"
              description="Run a sync to pull Jira issues into the vector database."
            />
          </Card>
        )
      )}

      {/* Store state */}
      {meta && (
        <Card
          title="Vector Store State"
          description="What the store currently holds and which model built it."
        >
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Last Sync" value={fmtDate(meta.last_sync_time)} />
            <Field label="Issues Indexed" value={formatNumber(meta.total_issues)} />
            <Field
              label="Embeddings"
              value={formatNumber(meta.total_embeddings)}
            />
            <Field
              label="Embedding Model"
              value={meta.embedding_version || "unknown"}
              mono
            />
          </dl>
          {!meta.embedding_version && meta.total_embeddings > 0 && (
            <p className="mt-4 rounded-lg border border-warn/30 bg-warn/10 px-3 py-2 text-xs text-warn">
              These vectors predate embedding-version tracking. Run a Full
              Rebuild so their provenance can be verified.
            </p>
          )}
        </Card>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="label">{label}</dt>
      <dd
        className={`mt-1 truncate text-sm text-content ${
          mono ? "font-mono text-xs" : ""
        }`}
        title={value}
      >
        {value}
      </dd>
    </div>
  );
}

function fmtDate(iso?: string): string {
  if (!iso) return "Never";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "Never" : d.toLocaleString();
}
