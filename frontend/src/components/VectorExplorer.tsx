import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api, RetrievedChunk } from "../api/client";
import {
  Badge,
  Card,
  EmptyState,
  ErrorBanner,
  PageHeader,
  ScoreBar,
  Spinner,
  StatCard,
  formatNumber,
} from "./ui";

export function VectorExplorer() {
  const [stats, setStats] = useState<{
    total_vectors: number;
    unique_issues: number;
  } | null>(null);
  const [docs, setDocs] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<RetrievedChunk[] | null>(
    null
  );
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [s, d] = await Promise.all([api.vectorStats(), api.listDocuments()]);
      setStats(s);
      setDocs(d);
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setSearchResults(await api.searchSimilar(searchQuery));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // Group chunks under their issue so the list reflects documents, not rows.
  const grouped = useMemo(() => {
    const map = new Map<string, any[]>();
    for (const d of docs) {
      const key = d.issue_key || "unknown";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(d);
    }
    const q = filter.trim().toLowerCase();
    return Array.from(map.entries())
      .filter(([key]) => !q || key.toLowerCase().includes(q))
      .sort(([a], [b]) => a.localeCompare(b));
  }, [docs, filter]);

  return (
    <div>
      <PageHeader
        title="Vector Database"
        subtitle="Inspect what is indexed and test retrieval directly, without invoking the LLM."
      />

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="Total Vectors"
          value={formatNumber(stats?.total_vectors)}
          tone="brand"
        />
        <StatCard
          label="Unique Issues"
          value={formatNumber(stats?.unique_issues)}
        />
        <StatCard
          label="Avg Chunks / Issue"
          value={
            stats?.unique_issues
              ? (stats.total_vectors / stats.unique_issues).toFixed(1)
              : "0"
          }
        />
        <StatCard label="Indexed Documents" value={formatNumber(docs.length)} />
      </div>

      {/* Similarity search — no LLM call, pure retrieval */}
      <Card
        title="Similarity Search"
        description="Embeds your query and ranks stored chunks by cosine similarity. No LLM tokens are spent."
        className="mb-6"
      >
        <div className="flex flex-wrap gap-2">
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="e.g. password reset flow"
            className="input min-w-[240px] flex-1"
            aria-label="Similarity search query"
          />
          <button
            onClick={handleSearch}
            disabled={loading || !searchQuery.trim()}
            className="btn-primary"
          >
            {loading && <Spinner />}
            Search
          </button>
        </div>

        {searchResults && (
          <div className="mt-4 space-y-2">
            {searchResults.length === 0 ? (
              <p className="text-sm text-content-muted">No matches found.</p>
            ) : (
              searchResults.map((r, i) => (
                <div
                  key={i}
                  className="rounded-lg border border-edge bg-surface-overlay p-3"
                >
                  <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-brand">
                        {r.issue_key}
                      </span>
                      <Badge>{r.issue_type}</Badge>
                    </div>
                    <ScoreBar score={r.similarity_score} />
                  </div>
                  <p className="whitespace-pre-wrap text-xs leading-relaxed text-content-muted">
                    {r.content}
                  </p>
                </div>
              ))
            )}
          </div>
        )}
      </Card>

      {/* Indexed documents */}
      <Card
        title={`Indexed Documents (${grouped.length})`}
        actions={
          docs.length > 0 && (
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter by issue key…"
              className="input w-44 py-1 text-xs"
              aria-label="Filter documents"
            />
          )
        }
      >
        {grouped.length === 0 ? (
          <EmptyState
            icon="◈"
            title={docs.length ? "No matches" : "Nothing indexed yet"}
            description={
              docs.length
                ? "No issue keys match that filter."
                : "Run a sync from the Sync tab to populate the vector database."
            }
          />
        ) : (
          <div className="space-y-2">
            {grouped.map(([issueKey, chunks]) => (
              <details
                key={issueKey}
                className="group rounded-lg border border-edge bg-surface-overlay"
              >
                <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-2.5">
                  <span className="text-content-subtle transition-transform group-open:rotate-90">
                    ›
                  </span>
                  <span className="font-mono text-sm font-semibold text-brand">
                    {issueKey}
                  </span>
                  <Badge>{chunks[0]?.issue_type || "—"}</Badge>
                  <span className="ml-auto text-xs text-content-subtle">
                    {chunks.length} chunk{chunks.length === 1 ? "" : "s"}
                  </span>
                </summary>
                <div className="space-y-2 border-t border-edge px-4 py-3">
                  {chunks
                    .sort((a, b) => (a.chunk_index ?? 0) - (b.chunk_index ?? 0))
                    .map((c, i) => (
                      <div key={i} className="text-xs">
                        <span className="font-mono text-content-subtle">
                          chunk {c.chunk_index ?? i}
                        </span>
                        {c.content && (
                          <p className="mt-0.5 whitespace-pre-wrap leading-relaxed text-content-muted">
                            {c.content}
                          </p>
                        )}
                      </div>
                    ))}
                </div>
              </details>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
