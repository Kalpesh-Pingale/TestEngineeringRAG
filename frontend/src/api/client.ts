import { ragLog, RagLogEntry } from "../lib/ragLog";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

/* ---------- Types ---------- */

export interface HealthCheck {
  ready: boolean;
  error?: string;
  fix?: string;
  [key: string]: any;
}

export interface Health {
  status: "ok" | "degraded" | "down";
  service: string;
  checks: Record<string, HealthCheck>;
}

export interface RetrievedChunk {
  content: string;
  issue_key: string;
  project_key: string;
  issue_type: string;
  similarity_score: number;
  metadata: Record<string, any>;
}

export interface RAGResponse {
  query: string;
  retrieved_chunks: RetrievedChunk[];
  prompt_sent: string;
  generated_response: string;
  total_tokens_used: number;
  target_chunk_count: number;
  context_chunk_count: number;
  baseline_tokens: number;
  retrieved_tokens: number;
  tokens_saved: number;
  indexed_chunk_count: number;
}

export interface TestCase {
  title: string;
  preconditions: string;
  steps: string[];
  expected_results: string;
  priority: string;
  test_type: string;
  automation_candidate: string;
  requirement: string;
  jira_issue_key: string;
}

export interface GeneratedTests {
  issue_key: string;
  test_cases: TestCase[];
  total_count: number;
  model_used: string;
  embedding_model: string;
  target_chunk_count: number;
  context_chunk_count: number;
  total_tokens_used: number;
  baseline_tokens: number;
  retrieved_tokens: number;
  tokens_saved: number;
  indexed_chunk_count: number;
}

export interface SyncResult {
  new_issues: number;
  updated_issues: number;
  deleted_issues: number;
  skipped_issues: number;
  total_tokens_saved: number;
  total_embeddings: number;
  last_sync_time: string;
}

export interface SyncStatus {
  is_running: boolean;
  progress: number;
  current_phase: string;
  result?: SyncResult;
}

export interface UploadResult {
  test_case_id?: number;
  testrail_url?: string;
  success: boolean;
  error?: string;
}

/* ---------- Transport ---------- */

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...options?.headers },
      ...options,
    });
  } catch {
    throw new ApiError(
      `Cannot reach the backend at ${API_BASE}. Start it with:\n  uvicorn app.main:app --reload --port 8000`,
      0
    );
  }

  if (!res.ok) {
    // FastAPI puts the actionable message in `detail`; surface that rather
    // than a raw status code, since most failures here are setup problems
    // with a specific remedy.
    let message = `Request failed (HTTP ${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) {
        message =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail);
      }
    } catch {
      /* non-JSON error body — keep the status message */
    }
    throw new ApiError(message, res.status);
  }

  return res.json();
}

/* ---------- RAG activity logging ---------- */

/**
 * Wrap a RAG call so it lands in the activity log whatever happens.
 *
 * Instrumenting here rather than in each component means every RAG call is
 * logged exactly once, including the ones made from Test Generation, and
 * failures are recorded with the backend's own message — the `409` remedies
 * are the most useful thing the log carries.
 */
async function logged<T>(
  op: string,
  startSummary: string,
  detail: RagLogEntry["detail"],
  call: () => Promise<T>,
  describe: (result: T) => { summary: string; detail?: RagLogEntry["detail"] }
): Promise<T> {
  const id = ragLog.start(op, startSummary, detail);
  const t0 = performance.now();
  try {
    const result = await call();
    const done = describe(result);
    ragLog.settle(
      id,
      "success",
      done.summary,
      performance.now() - t0,
      done.detail
    );
    return result;
  } catch (e: any) {
    const status = e instanceof ApiError ? e.status : 0;
    ragLog.settle(id, "error", e?.message ?? "Request failed", performance.now() - t0, {
      status: status === 0 ? "unreachable" : status,
    });
    throw e;
  }
}

/** Retrieval quality in one number — the reason most results disappoint. */
function topScore(chunks: RetrievedChunk[]): string {
  if (chunks.length === 0) return "—";
  return `${(Math.max(...chunks.map((c) => c.similarity_score)) * 100).toFixed(1)}%`;
}

/* ---------- Endpoints ---------- */

export const api = {
  health: () => request<Health>("/api/health"),
  getConfig: () => request<any>("/api/config/"),

  // Sync
  fullSync: (projectKey?: string, issueTypes?: string[]) =>
    request<SyncResult>("/api/sync/full", {
      method: "POST",
      body: JSON.stringify({ project_key: projectKey, issue_types: issueTypes }),
    }),
  incrementalSync: (projectKey?: string, issueTypes?: string[]) =>
    request<SyncResult>("/api/sync/incremental", {
      method: "POST",
      body: JSON.stringify({ project_key: projectKey, issue_types: issueTypes }),
    }),
  syncStatus: () => request<SyncStatus>("/api/sync/status"),
  syncMetadata: () => request<any>("/api/sync/metadata"),

  // Vector store
  vectorStats: () =>
    request<{ total_vectors: number; unique_issues: number }>(
      "/api/vector/stats"
    ),
  listDocuments: () => request<any[]>("/api/vector/documents"),
  searchSimilar: (query: string, topK = 5) =>
    logged(
      "vector.search",
      `Similarity search — "${query}"`,
      { top_k: topK },
      () =>
        request<RetrievedChunk[]>("/api/vector/search", {
          method: "POST",
          body: JSON.stringify({ query, top_k: topK }),
        }),
      (chunks) => ({
        summary: `Similarity search returned ${chunks.length} chunk${
          chunks.length === 1 ? "" : "s"
        }`,
        detail: { chunks: chunks.length, top_score: topScore(chunks) },
      })
    ),

  // RAG
  ragQuery: (query: string, topK = 5) =>
    logged(
      "rag.query",
      `Query — "${query}"`,
      { top_k: topK },
      () =>
        request<RAGResponse>("/api/rag/query", {
          method: "POST",
          body: JSON.stringify({ query, top_k: topK }),
        }),
      (r) => ({
        summary: `Answered from ${r.retrieved_chunks.length} chunk${
          r.retrieved_chunks.length === 1 ? "" : "s"
        }`,
        detail: {
          chunks: r.retrieved_chunks.length,
          top_score: topScore(r.retrieved_chunks),
          tokens: r.total_tokens_used,
        },
      })
    ),
  generateTests: (issueKey: string) =>
    logged(
      "rag.generate-tests",
      `Generate tests — ${issueKey}`,
      {},
      () =>
        request<GeneratedTests>("/api/rag/generate-tests", {
          method: "POST",
          body: JSON.stringify({ issue_key: issueKey }),
        }),
      (r) => ({
        summary: `Generated ${r.total_count} test case${
          r.total_count === 1 ? "" : "s"
        } for ${r.issue_key}`,
        detail: {
          target_chunks: r.target_chunk_count,
          context_chunks: r.context_chunk_count,
          tokens: r.total_tokens_used,
          model: r.model_used,
        },
      })
    ),
  findSimilar: (issueKey: string, topK = 5) =>
    logged(
      "rag.similar",
      `Find similar to ${issueKey}`,
      { top_k: topK },
      () =>
        request<RAGResponse>("/api/rag/similar", {
          method: "POST",
          body: JSON.stringify({ issue_key: issueKey, top_k: topK }),
        }),
      (r) => ({
        summary: `Found ${r.retrieved_chunks.length} similar chunk${
          r.retrieved_chunks.length === 1 ? "" : "s"
        }`,
        detail: {
          chunks: r.retrieved_chunks.length,
          top_score: topScore(r.retrieved_chunks),
        },
      })
    ),
  semanticSearch: (query: string, topK = 5) =>
    logged(
      "rag.semantic-search",
      `Semantic search — "${query}"`,
      { top_k: topK },
      () =>
        request<RAGResponse>("/api/rag/semantic-search", {
          method: "POST",
          body: JSON.stringify({ query, top_k: topK }),
        }),
      (r) => ({
        summary: `Semantic search returned ${r.retrieved_chunks.length} chunk${
          r.retrieved_chunks.length === 1 ? "" : "s"
        }`,
        detail: {
          chunks: r.retrieved_chunks.length,
          top_score: topScore(r.retrieved_chunks),
        },
      })
    ),

  // TestRail
  uploadTestCases: (testCases: TestCase[], sectionId?: number) =>
    request<UploadResult[]>("/api/testrail/upload", {
      method: "POST",
      body: JSON.stringify({ test_cases: testCases, section_id: sectionId }),
    }),
  uploadGenerated: (generated: GeneratedTests, sectionId?: number) =>
    request<UploadResult[]>("/api/testrail/upload-generated", {
      method: "POST",
      body: JSON.stringify({ generated, section_id: sectionId }),
    }),
};
