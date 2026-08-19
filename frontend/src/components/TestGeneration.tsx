import React, { useEffect, useMemo, useState } from "react";
import { api, GeneratedTests, GroqModel, TestCase, UploadResult } from "../api/client";
import {
  Badge,
  Card,
  EmptyState,
  ErrorBanner,
  PageHeader,
  Spinner,
  StatCard,
  formatNumber,
} from "./ui";

const PRIORITY_TONE: Record<string, string> = {
  High: "danger",
  Medium: "warn",
  Low: "ok",
};

export function TestGeneration() {
  const [issueKey, setIssueKey] = useState("");
  const [models, setModels] = useState<GroqModel[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GeneratedTests | null>(null);
  const [uploadResults, setUploadResults] = useState<UploadResult[] | null>(null);
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  useEffect(() => {
    // Non-blocking: if this fails (e.g. no GROQ_API_KEY yet), the dropdown just
    // falls back to "configured default" and generation still works.
    api.getModels().then(setModels).catch(() => setModels([]));
  }, []);

  const handleGenerate = async () => {
    if (!issueKey.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setUploadResults(null);
    setExpanded(new Set());
    setTypeFilter("all");
    try {
      setResult(
        await api.generateTests(issueKey.trim().toUpperCase(), selectedModel)
      );
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    if (!result?.test_cases?.length) return;
    setUploading(true);
    setError(null);
    try {
      setUploadResults(await api.uploadGenerated(result));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const testTypes = useMemo(
    () => Array.from(new Set(result?.test_cases.map((t) => t.test_type) ?? [])),
    [result]
  );

  const visible = useMemo(
    () =>
      (result?.test_cases ?? []).filter(
        (t) => typeFilter === "all" || t.test_type === typeFilter
      ),
    [result, typeFilter]
  );

  const toggle = (i: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });

  const exportCsv = () => {
    if (!result) return;
    const esc = (s: string) => `"${String(s ?? "").replace(/"/g, '""')}"`;
    const rows = [
      ["#", "Title", "Type", "Priority", "Automation", "Preconditions", "Steps", "Expected Results"],
      ...result.test_cases.map((t, i) => [
        String(i + 1),
        t.title,
        t.test_type,
        t.priority,
        t.automation_candidate,
        t.preconditions,
        t.steps.map((s, si) => `${si + 1}. ${s}`).join("\n"),
        t.expected_results,
      ]),
    ];
    const blob = new Blob([rows.map((r) => r.map(esc).join(",")).join("\n")], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${result.issue_key}-test-cases.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <PageHeader
        title="Test Generation"
        subtitle="Generate test cases for a Jira issue using retrieved context, then push them to TestRail."
      />

      {/* Input */}
      <Card className="mb-6">
        <div className="flex flex-wrap gap-2">
          <input
            value={issueKey}
            onChange={(e) => setIssueKey(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleGenerate()}
            placeholder="Jira issue key (e.g. SCRUM-17)"
            className="input min-w-[220px] flex-1 font-mono uppercase"
            aria-label="Jira issue key"
          />
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="select w-auto"
            aria-label="LLM model"
            title="Pick a different model if the configured default is deprecated or fails"
          >
            <option value="">Use configured default</option>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id}
              </option>
            ))}
          </select>
          <button
            onClick={handleGenerate}
            disabled={loading || !issueKey.trim()}
            className="btn-primary"
          >
            {loading && <Spinner />}
            {loading ? "Generating…" : "Generate Tests"}
          </button>
          {!!result?.test_cases.length && (
            <>
              <button onClick={exportCsv} className="btn-secondary">
                Export CSV
              </button>
              <button
                onClick={handleUpload}
                disabled={uploading}
                className="btn-accent"
              >
                {uploading && <Spinner />}
                {uploading ? "Uploading…" : "Upload to TestRail"}
              </button>
            </>
          )}
        </div>
      </Card>

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      {loading && (
        <Card>
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="skeleton h-14 w-full" />
            ))}
          </div>
        </Card>
      )}

      {/* Upload results */}
      {uploadResults && (
        <Card title="TestRail Upload" className="mb-6">
          <div className="space-y-1.5">
            {uploadResults.map((ur, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className={ur.success ? "text-ok" : "text-danger"}>
                  {ur.success ? "✓" : "✕"}
                </span>
                <span className="text-content-muted">
                  {ur.success
                    ? `Created TestRail case #${ur.test_case_id}`
                    : ur.error}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Test Cases"
              value={result.total_count}
              tone="brand"
            />
            <StatCard
              label="Context Used"
              value={`${result.target_chunk_count} + ${result.context_chunk_count}`}
              hint="target issue + related"
            />
            <StatCard
              label="Tokens This Call"
              value={formatNumber(result.total_tokens_used)}
              hint={result.model_used}
            />
            <StatCard
              label="Tokens Saved"
              value={formatNumber(result.tokens_saved)}
              tone={result.tokens_saved > 0 ? "ok" : "default"}
              hint={
                result.baseline_tokens === 0
                  ? "Re-sync this issue to enable this estimate"
                  : result.tokens_saved > 0
                  ? `≈${formatNumber(result.baseline_tokens)} tok if fetched live via MCP (tentative)`
                  : "RAG context already ≥ a direct fetch"
              }
            />
          </div>

          <Card
            title={`Generated Test Cases (${visible.length}${
              typeFilter !== "all" ? ` of ${result.total_count}` : ""
            })`}
            description="One row per test case. Click a row to expand full steps."
            actions={
              testTypes.length > 1 && (
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="select w-auto py-1 text-xs"
                  aria-label="Filter by test type"
                >
                  <option value="all">All types ({result.total_count})</option>
                  {testTypes.map((t) => (
                    <option key={t} value={t}>
                      {t} (
                      {result.test_cases.filter((c) => c.test_type === t).length})
                    </option>
                  ))}
                </select>
              )
            }
            className="p-0"
          >
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    <th className="th w-10">#</th>
                    <th className="th min-w-[240px]">Test Case</th>
                    <th className="th min-w-[160px]">Preconditions</th>
                    <th className="th min-w-[280px]">Steps</th>
                    <th className="th min-w-[180px]">Expected Result</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((tc, i) => {
                    const isOpen = expanded.has(i);
                    const showAll = isOpen || tc.steps.length <= 4;
                    const steps = showAll ? tc.steps : tc.steps.slice(0, 4);
                    return (
                      <tr
                        key={i}
                        onClick={() => toggle(i)}
                        className="cursor-pointer border-b border-edge transition-colors last:border-0 hover:bg-surface-overlay/50"
                      >
                        <td className="td font-mono text-xs text-content-subtle">
                          {i + 1}
                        </td>
                        <td className="td">
                          <p className="font-semibold text-content">{tc.title}</p>
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            <Badge tone="accent">{tc.test_type}</Badge>
                            <Badge tone={PRIORITY_TONE[tc.priority] || "neutral"}>
                              {tc.priority}
                            </Badge>
                            <Badge
                              tone={
                                tc.automation_candidate === "Yes"
                                  ? "ok"
                                  : "neutral"
                              }
                            >
                              {tc.automation_candidate === "Yes"
                                ? "Automatable"
                                : "Manual"}
                            </Badge>
                          </div>
                        </td>
                        <td className="td text-content-muted">
                          {tc.preconditions || (
                            <span className="text-content-subtle">—</span>
                          )}
                        </td>
                        <td className="td">
                          {steps.length ? (
                            <ol className="list-decimal space-y-1 pl-4 text-content-muted marker:text-content-subtle">
                              {steps.map((s, si) => (
                                <li key={si} className="leading-relaxed">
                                  {s}
                                </li>
                              ))}
                            </ol>
                          ) : (
                            <span className="text-content-subtle">—</span>
                          )}
                          {!showAll && (
                            <button className="mt-1 text-xs font-medium text-brand hover:underline">
                              +{tc.steps.length - 4} more steps
                            </button>
                          )}
                        </td>
                        <td className="td text-content-muted">
                          {tc.expected_results}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      {!result && !loading && !error && (
        <Card>
          <EmptyState
            icon="✓"
            title="No test cases yet"
            description="Enter a Jira issue key above. The issue must be synced into the vector database first."
          />
        </Card>
      )}
    </div>
  );
}
