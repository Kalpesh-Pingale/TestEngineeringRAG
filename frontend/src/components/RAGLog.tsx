import React, { useSyncExternalStore } from "react";
import { ragLog, RagLogEntry } from "../lib/ragLog";
import { Badge, EmptyState } from "./ui";

/** Subscribe to the RAG activity log. */
export function useRagLog(): RagLogEntry[] {
  return useSyncExternalStore(ragLog.subscribe, ragLog.getSnapshot, ragLog.getSnapshot);
}

const LEVEL: Record<
  RagLogEntry["level"],
  { icon: string; dot: string; text: string; badge: string }
> = {
  pending: {
    icon: "…",
    dot: "bg-warn animate-pulse",
    text: "text-content-muted",
    badge: "warn",
  },
  success: { icon: "✓", dot: "bg-ok", text: "text-content", badge: "ok" },
  error: { icon: "✕", dot: "bg-danger", text: "text-danger", badge: "danger" },
};

function time(ts: number): string {
  return new Date(ts).toLocaleTimeString(undefined, { hour12: false });
}

function duration(ms?: number): string | null {
  if (ms == null) return null;
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

/**
 * Chronological log of every RAG call made this session.
 *
 * Complements the single-query trace above it: the trace explains one result,
 * the log shows the sequence — which query was slow, which returned nothing,
 * and the exact backend message behind a failure.
 */
export function RAGLog({ className = "" }: { className?: string }) {
  const entries = useRagLog();
  const errors = entries.filter((e) => e.level === "error").length;

  return (
    <section className={`card ${className}`}>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-edge px-5 py-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-content">Activity Log</h3>
          <Badge>{entries.length}</Badge>
          {errors > 0 && <Badge tone="danger">{errors} failed</Badge>}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-content-subtle">
            This session only · never leaves the browser
          </span>
          <button
            onClick={() => ragLog.clear()}
            disabled={entries.length === 0}
            className="btn-ghost px-2 py-1 text-xs disabled:opacity-40"
          >
            Clear
          </button>
        </div>
      </header>

      {entries.length === 0 ? (
        <EmptyState
          icon="≡"
          title="No RAG activity yet"
          description="Every query, semantic search, and test generation is recorded here with its duration, retrieval quality, and token count."
        />
      ) : (
        <ol className="max-h-80 divide-y divide-edge overflow-auto">
          {entries.map((e) => {
            const tone = LEVEL[e.level];
            return (
              <li key={e.id} className="flex gap-3 px-5 py-2.5">
                <span
                  className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${tone.dot}`}
                  aria-hidden="true"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span className="font-mono text-[11px] tabular-nums text-content-subtle">
                      {time(e.ts)}
                    </span>
                    <span className="font-mono text-[11px] text-accent">
                      {e.op}
                    </span>
                    {duration(e.durationMs) && (
                      <span className="font-mono text-[11px] tabular-nums text-content-subtle">
                        {duration(e.durationMs)}
                      </span>
                    )}
                  </div>
                  <p
                    className={`mt-0.5 whitespace-pre-wrap break-words text-xs leading-relaxed ${tone.text}`}
                  >
                    <span aria-hidden="true">{tone.icon} </span>
                    {e.summary}
                  </p>
                  {e.detail && Object.keys(e.detail).length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {Object.entries(e.detail).map(([k, v]) => (
                        <span
                          key={k}
                          className="rounded border border-edge bg-surface-overlay px-1.5 py-0.5 font-mono text-[10px] text-content-muted"
                        >
                          {k}={String(v)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
