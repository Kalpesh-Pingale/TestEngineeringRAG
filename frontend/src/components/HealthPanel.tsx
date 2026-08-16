import React from "react";
import { Health } from "../api/client";
import { Badge, Spinner } from "./ui";

const LABELS: Record<string, string> = {
  embeddings: "Embedding model",
  vector_store: "Vector store",
  llm: "LLM (generation)",
  jira: "Jira connection",
  testrail: "TestRail",
};

const REQUIRED = new Set(["embeddings", "vector_store", "llm"]);

/** Fields that are noise in the UI — either shown elsewhere or internal. */
const HIDDEN_FIELDS = new Set(["ready", "error", "fix", "reason", "compatible"]);

export function HealthPanel({
  health,
  onClose,
  onRefresh,
}: {
  health: Health | null;
  onClose: () => void;
  onRefresh: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-md flex-col border-l border-edge bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="System diagnostics"
      >
        <header className="flex items-center justify-between border-b border-edge px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-content">
              System Diagnostics
            </h2>
            <p className="text-xs text-content-muted">
              Every dependency the RAG pipeline needs
            </p>
          </div>
          <div className="flex gap-2">
            <button onClick={onRefresh} className="btn-ghost px-2 py-1 text-xs">
              Refresh
            </button>
            <button
              onClick={onClose}
              className="btn-ghost px-2 py-1"
              aria-label="Close"
            >
              ✕
            </button>
          </div>
        </header>

        <div className="flex-1 space-y-3 overflow-y-auto p-5">
          {!health && (
            <div className="flex items-center gap-2 text-sm text-content-muted">
              <Spinner /> Checking…
            </div>
          )}

          {health?.status === "down" && (
            <div className="rounded-lg border border-danger/30 bg-danger/10 p-4">
              <p className="text-sm font-semibold text-danger">
                Backend unreachable
              </p>
              <p className="mt-1 text-xs text-content-muted">
                Start the API from the <code>backend/</code> directory:
              </p>
              <pre className="mt-2 overflow-x-auto rounded bg-canvas p-2 font-mono text-[11px] text-content">
                uvicorn app.main:app --reload --port 8000
              </pre>
            </div>
          )}

          {health &&
            Object.entries(health.checks).map(([key, check]) => {
              const required = REQUIRED.has(key);
              return (
                <div key={key} className="card p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`h-2 w-2 rounded-full ${
                          check.ready
                            ? "bg-ok"
                            : required
                            ? "bg-danger"
                            : "bg-content-subtle"
                        }`}
                      />
                      <span className="text-sm font-medium text-content">
                        {LABELS[key] || key}
                      </span>
                    </div>
                    <Badge
                      tone={check.ready ? "ok" : required ? "danger" : "neutral"}
                    >
                      {check.ready ? "Ready" : required ? "Blocked" : "Optional"}
                    </Badge>
                  </div>

                  {check.error && (
                    <p className="mt-2 text-xs leading-relaxed text-danger">
                      {check.error}
                    </p>
                  )}
                  {check.reason && (
                    <p className="mt-2 text-xs leading-relaxed text-warn">
                      {check.reason}
                    </p>
                  )}
                  {check.fix && (
                    <pre className="mt-2 overflow-x-auto rounded bg-canvas p-2 font-mono text-[11px] text-brand">
                      {check.fix}
                    </pre>
                  )}

                  {/* Remaining scalar fields as a compact key/value list */}
                  <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
                    {Object.entries(check)
                      .filter(
                        ([k, v]) =>
                          !HIDDEN_FIELDS.has(k) &&
                          v !== "" &&
                          v !== null &&
                          v !== undefined &&
                          typeof v !== "object"
                      )
                      .map(([k, v]) => (
                        <React.Fragment key={k}>
                          <dt className="text-[11px] text-content-subtle">{k}</dt>
                          <dd className="truncate font-mono text-[11px] text-content-muted">
                            {String(v)}
                          </dd>
                        </React.Fragment>
                      ))}
                  </dl>
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
}
