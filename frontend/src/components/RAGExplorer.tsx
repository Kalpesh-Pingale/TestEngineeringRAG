import React, { useState } from "react";
import { api, RAGResponse } from "../api/client";
import { RAGLog } from "./RAGLog";
import {
  Badge,
  Card,
  EmptyState,
  ErrorBanner,
  PageHeader,
  ScoreBar,
  Spinner,
  formatNumber,
} from "./ui";

/** The pipeline stages, rendered as a vertical trace of one query. */
const STAGES = [
  { key: "query", label: "User Query", tone: "brand" },
  { key: "chunks", label: "Retrieved Chunks", tone: "accent" },
  { key: "prompt", label: "Prompt Sent to LLM", tone: "warn" },
  { key: "response", label: "Generated Response", tone: "ok" },
] as const;

export function RAGExplorer() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [result, setResult] = useState<RAGResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);

  const handleQuery = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.ragQuery(query, topK));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="RAG Explorer"
        subtitle="Trace a single query through the pipeline — what was retrieved, what the model was asked, and what it returned."
      />

      <Card className="mb-6">
        <div className="flex flex-wrap gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleQuery()}
            placeholder="e.g. what happens when login fails?"
            className="input min-w-[240px] flex-1"
            aria-label="RAG query"
          />
          <select
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="select w-auto"
            aria-label="Number of chunks to retrieve"
          >
            {[3, 5, 7, 10].map((n) => (
              <option key={n} value={n}>
                Top {n}
              </option>
            ))}
          </select>
          <button
            onClick={handleQuery}
            disabled={loading || !query.trim()}
            className="btn-primary"
          >
            {loading && <Spinner />}
            {loading ? "Querying…" : "Run Query"}
          </button>
        </div>
      </Card>

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      {loading && (
        <div className="space-y-3">
          {STAGES.map((s) => (
            <div key={s.key} className="skeleton h-24 w-full rounded-xl" />
          ))}
        </div>
      )}

      {result && !loading && (
        <div className="space-y-3">
          {/* Stage 1 — query */}
          <Stage index={1} label="User Query" tone="brand">
            <p className="text-sm text-content">{result.query}</p>
          </Stage>

          {/* Stage 2 — retrieval */}
          <Stage
            index={2}
            label={`Retrieved Chunks (${result.retrieved_chunks.length})`}
            tone="accent"
          >
            {result.retrieved_chunks.length === 0 ? (
              <p className="text-sm text-content-muted">
                Nothing retrieved — the vector store may be empty.
              </p>
            ) : (
              <div className="space-y-2">
                {result.retrieved_chunks.map((c, i) => (
                  <div
                    key={i}
                    className="rounded-lg border border-edge bg-surface-overlay p-3"
                  >
                    <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-accent">
                          {c.issue_key}
                        </span>
                        <Badge>{c.issue_type}</Badge>
                      </div>
                      <ScoreBar score={c.similarity_score} />
                    </div>
                    <p className="whitespace-pre-wrap text-xs leading-relaxed text-content-muted">
                      {c.content}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </Stage>

          {/* Stage 3 — prompt */}
          <Stage
            index={3}
            label="Prompt Sent to LLM"
            tone="warn"
            action={
              <button
                onClick={() => setShowPrompt((v) => !v)}
                className="btn-ghost px-2 py-1 text-xs"
              >
                {showPrompt ? "Collapse" : "Expand"}
              </button>
            }
          >
            <pre
              className={`overflow-auto whitespace-pre-wrap rounded-lg bg-canvas p-3 font-mono text-[11px] leading-relaxed text-content-muted ${
                showPrompt ? "max-h-none" : "max-h-52"
              }`}
            >
              {result.prompt_sent}
            </pre>
            <p className="mt-2 text-xs text-content-subtle">
              ≈{formatNumber(Math.round(result.prompt_sent.length / 4))} tokens
              of prompt
            </p>
          </Stage>

          {/* Stage 4 — response */}
          <Stage index={4} label="Generated Response" tone="ok">
            <div className="whitespace-pre-wrap text-sm leading-relaxed text-content">
              {result.generated_response}
            </div>
            {result.total_tokens_used > 0 && (
              <p className="mt-3 border-t border-edge pt-3 text-xs text-content-subtle">
                {formatNumber(result.total_tokens_used)} tokens used this call
              </p>
            )}
          </Stage>
        </div>
      )}

      {!result && !loading && !error && (
        <Card>
          <EmptyState
            icon="◎"
            title="Run a query to see the pipeline"
            description="Every stage is shown: retrieval, similarity scores, the exact prompt, and the model's response."
          />
        </Card>
      )}

      {/* Session log — the trace above explains one call, this shows the
          sequence, including calls made from the Test Generation tab. */}
      <RAGLog className="mt-6" />
    </div>
  );
}

function Stage({
  index,
  label,
  tone,
  action,
  children,
}: {
  index: number;
  label: string;
  tone: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  const border: Record<string, string> = {
    brand: "border-l-brand",
    accent: "border-l-accent",
    warn: "border-l-warn",
    ok: "border-l-ok",
  };
  const text: Record<string, string> = {
    brand: "text-brand",
    accent: "text-accent",
    warn: "text-warn",
    ok: "text-ok",
  };
  return (
    <section className={`card border-l-2 ${border[tone]} animate-fade-up`}>
      <header className="flex items-center justify-between gap-2 px-5 py-3">
        <h3 className="flex items-center gap-2">
          <span className="font-mono text-xs text-content-subtle">{index}</span>
          <span
            className={`text-[11px] font-semibold uppercase tracking-wider ${text[tone]}`}
          >
            {label}
          </span>
        </h3>
        {action}
      </header>
      <div className="px-5 pb-5">{children}</div>
    </section>
  );
}
