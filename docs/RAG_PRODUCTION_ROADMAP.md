# RAG Platform — Production Roadmap

## Problem Statement

The current vibe-coding approach (Jira MCP → LLM → TestRail MCP) works but has two fundamental limitations:

1. **High token consumption** — Every test generation call fetches full Jira issues (descriptions, comments, history) and sends them to the LLM. For 30+ projects, this repeats the same data constantly.
2. **No memory** — The LLM has no persistent knowledge of past issues, test patterns, or defect history. Each call is stateless and can't learn from previous mistakes.

This RAG system solves both by indexing Jira data into a vector database once and retrieving only the most relevant chunks per query.

---

## Status — what changed after the correctness audit

An audit before scaling found the retrieval layer was **not functioning at all**. The
issues below are fixed; they are recorded here because the roadmap's phases assumed a
working baseline that did not exist.

| Finding | Impact | Status |
|---|---|---|
| Embedding model was never reachable; every vector was a hash-based placeholder | Retrieval was random. Measured pairwise cosine: mean **-0.14**, max **0.05** (real: **0.62–0.83**) | Fixed — fastembed, failures now raise |
| Target issue not guaranteed in retrieved context | Tests could be generated for the wrong story | Fixed — exact-match stage 1 |
| LLM asked for prose, parsed with regex | Test cases collapsed into one paragraph | Fixed — strict JSON contract |
| No embedding-version tracking | Model change silently corrupts search | Fixed — stamped + mismatch guard |
| `tokens_saved` measured skipped *embedding* work | Headline metric measured the wrong thing | Fixed — baseline vs retrieved |
| Vector store rewrote the entire file per chunk | O(n²) writes during sync | Fixed — batched flush |
| Jira content injected into prompts unsanitized | Prompt injection via ticket description | Mitigated |

**Lesson for the roadmap**: these were invisible without evaluation. Phase 0 exists so
the next such failure is caught by a test rather than by noticing that output "feels off."

---

## Architecture Overview

```
                    ┌──────────────────┐
                    │  MCP Client Apps  │  ← Team's vibe-coding solutions
                    │  (Cursor, Claude, │     connect here
                    │   custom agents)  │
                    └────────┬─────────┘
                             │ MCP Protocol (stdio/HTTP)
                    ┌────────▼─────────┐
                    │   RAG MCP Server  │  ← Wrap RAG pipeline as MCP tools
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼─────┐ ┌─────▼──────┐ ┌─────▼──────┐
     │  Vector DB   │ │ Embeddings │ │  LLM       │
     │  per project │ │ (fastembed │ │ (Groq)     │
     │              │ │  local ONNX)│ │            │
     └──────────────┘ └────────────┘ └────────────┘
              │
     ┌────────▼─────┐
     │  Sync Engine │ ← Periodically syncs Jira → vector DB
     └──────────────┘
```

### Token Comparison

| Approach | Per Test Generation Call |
|---|---|
| Direct Jira → LLM | 8,000–15,000 tokens (full issue + comments) |
| RAG (this system) | 800–2,000 tokens (3–5 relevant chunks) |
| **Savings** | **80–90%** |

> **Measure this, don't assume it.** Savings scale with corpus size and are
> legitimately **zero** while the corpus is smaller than `top_k` — with 4 issues
> indexed and `top_k=5`, retrieval returns everything, so nothing is saved. The
> API reports `baseline_tokens`, `retrieved_tokens`, and `tokens_saved` per call;
> validate the 80–90% claim against those numbers once a real project is indexed
> before repeating it to stakeholders.

---

## Phase 0 — Correctness & Evaluation (Est. 2–3 days) ← **do this first**

**Goal**: Make retrieval quality measurable, so regressions surface as failing tests
rather than as vague dissatisfaction with output. Everything after this multiplies
whatever quality exists here across 30 projects — including its defects.

### What to Build

**1. Retrieval evaluation harness** (`backend/eval/`)

A fixture set of ~20 queries with known-correct issue keys:

```python
CASES = [
    {"query": "how does a user sign in",        "expect": "SCRUM-17"},
    {"query": "creating a new account",          "expect": "SCRUM-16"},
    {"query": "searching the product catalogue", "expect": "SCRUM-18"},
]
```

Report and gate on:
- **Recall@k** — is the expected issue in the top-k? Target ≥ 0.9 at k=5.
- **MRR** — how highly does it rank?
- **Similarity floor** — flag when the best match scores < 0.45; usually means
  nothing relevant is indexed.

A smoke assertion worth keeping permanently: *related issues must score higher than
unrelated ones.* That single check would have caught the placeholder-embedding bug
on day one.

**2. Groundedness check for generation**

For each generated test case, verify its key terms appear in the retrieved context.
Cases that don't are hallucinated requirements — the most damaging failure mode here,
because a plausible-looking invented test wastes QA time downstream.

**3. Field-aware chunking** (see `prompt/PROMPT_REVIEW.md` §7)

Current chunking concatenates all fields and splits every 800 chars, so acceptance
criteria get split mid-list and only chunk 0 carries the issue summary. Chunk per
field and prefix every chunk with `{issue_key}: {summary}`.

**Exit criteria**: `python -m eval.run` prints Recall@5 ≥ 0.9 on the fixture set, and
CI fails if it drops.

---

## Phase 1 — Wrap RAG as an MCP Server (Est. 1–2 days)

**Goal**: Package the RAG pipeline as an MCP server the team can connect to from any
MCP-compatible client.

### What to Build

A Python MCP server (`mcp_rag_server/`) exposing:

| Tool | Description | Input | Output |
|---|---|---|---|
| `sync_project` | Sync a Jira project into the vector DB | `project_key`, `mode` (full/incremental) | Sync result with counts |
| `generate_tests` | Generate test cases using RAG | `issue_key`, `project_key` | Structured test cases |
| `query_rag` | Generic RAG query | `query`, `project_key`, `top_k` | Retrieved chunks + LLM response |
| `search_similar` | Semantic search, no LLM call | `query`, `project_key`, `top_k` | Chunks with scores |
| `health` | Readiness of embeddings / store / LLM | — | Per-component status |

Include `health` from the start. Without it, a misconfigured client gets bad results
with no indication why — exactly the failure mode Phase 0 exists to prevent.

### Implementation Notes

- Use [FastMCP](https://github.com/jlowin/fastmcp) or the official `mcp` Python SDK
- Reuses existing services: `RAGService`, `VectorStore`, `SyncService`, `TestGenerator`, `EmbeddingService`
- Every tool accepts `project_key` even though Phase 1 runs one project — this prepares for Phase 2
- Surface `RAGError` / `EmbeddingError` as tool errors with their remediation text intact

### Team Integration

Local (stdio transport — no port, the client spawns the process):

```json
{
  "mcpServers": {
    "rag-engine": {
      "command": "python",
      "args": ["-m", "mcp_rag_server.server"]
    }
  }
}
```

Hosted (HTTP transport, after Phase 3):

```json
{
  "mcpServers": {
    "rag-engine": { "url": "http://rag-server:8100/mcp" }
  }
}
```

> Note: stdio and HTTP are alternative transports. A stdio server has no port, so
> don't pass `--port` in the `command` form.

---

## Phase 2 — Historical Knowledge: Index TestRail (Est. 2–3 days)

**Goal**: Make the system improve as it is used. This is the "train the RAG with
historic data" objective, and it is the highest-leverage feature remaining.

Retrieval currently supplies only Jira *requirements*. The most valuable corpus for
writing test cases is the set of test cases the team has already written and accepted.

### What to Build

**1. TestRail ingestion** — pull existing cases via the TestRail API, chunk, embed
into the same store with `source="testrail"`, and keep the Jira reference field as
the link back to the originating issue.

**2. Exemplar retrieval** — extend generation to a third retrieval stage:

| Stage | Source | Role in prompt |
|---|---|---|
| 1 | Target Jira issue (exact match) | The specification under test |
| 2 | Related Jira issues (semantic) | Coverage hints, prior defects |
| 3 | **Accepted TestRail cases (semantic)** | **Few-shot exemplars — house style, depth, phrasing** |

The model stops inventing a format and starts matching the team's.

**3. Acceptance feedback loop** — record per generated case whether it was uploaded
unedited, edited, or discarded. Prefer unedited-accepted cases as exemplars. Over
time the system converges on what this team actually approves.

**4. Upload idempotency** — match on the Jira reference field before creating, so
re-running generation updates or skips instead of duplicating every case.

**Why before multi-project**: it improves output quality for the project you have
today, and the retrieval changes are far easier to validate against one corpus.

---

## Phase 3 — Multi-Project Support (Est. 3–4 days)

**Goal**: Support 30+ projects with isolated vector stores, per-project sync, and
project-scoped queries.

### Changes Required

**1. Per-project vector stores**

```
chromadb/
├── project-alpha/{vectors.npy, metadata.jsonl, sync_metadata.json}
├── project-beta/{...}
```

- `VectorStore` takes `project_key` → stores under `chromadb/{project_key}/`
- All operations scoped to that project's storage; search logic unchanged

**2. Per-project sync** — `SyncMetadata` becomes one file per project; incremental
sync tracks last-sync-time per project independently.

**3. Project-scoped RAG** — `RAGService.query()` and `generate_test_cases()` accept
`project_key`. Resolve `PROJ-123` to its project via the key prefix, or require an
explicit `project_key`.

**4. Embedding consistency across projects** — all projects must share one embedding
model. The per-project store makes it possible to have mismatched models silently;
the version guard must run per project on startup and report which need rebuilding.

**5. Config management**

Option A — central `projects.yaml` (simpler for internal deployment):

```yaml
projects:
  project-alpha:
    jira_base_url: https://alpha.atlassian.net
    jira_email: user@alpha.com
    jira_api_token: ${ALPHA_TOKEN}   # env indirection, never inline secrets
```

Option B — per-request credentials (more flexible for cross-team use).

### Migration Path

1. Add `project_key` to `VectorStore.__init__()`
2. Add `project_key` to `SyncService` methods
3. Add `project_key` to `RAGService` methods
4. Update router endpoints to accept `project_key`
5. Migration script: move `chromadb/` → `chromadb/{project_key}/`
6. Re-run the Phase 0 eval per project

---

## Phase 4 — Hosted Shared Server (Est. 2–3 days)

**Goal**: Deploy centrally so the team shares one always-on instance and vector DB.

### Deployment

- Any cloud VM or on-prem box (2 CPU, 4GB RAM, 20GB disk)
- `uvicorn`/`gunicorn` behind nginx or Caddy
- Cron or background scheduler running incremental syncs every 30–60 min per project

### Authentication

API key middleware, scoped per team:

```python
API_KEYS = {"team-key-1": {"projects": ["alpha", "beta"]}}
```

Add this in **Phase 1**, not here — an unauthenticated service that proxies an LLM
billing account is a standing liability the moment it leaves localhost.

### Concurrency

The file-backed store is single-writer. Concurrent syncs on one project can interleave
writes; serialize with a per-project lock before multiple users share an instance.

| Option | Pros | Cons |
|---|---|---|
| File-based (current) | Zero deps, fast for <50k vectors | Single-writer, full rewrite per flush |
| ChromaDB server mode | Same API, real concurrency | Extra service |
| Qdrant (docker) | High performance, multi-tenant | Extra service to maintain |
| PostgreSQL + pgvector | Battle-tested, transactional | Schema work, different query API |

Move when sync contention or store size actually bites — not before.

### Observability

Log per generation call: issue key, chunks retrieved, top similarity score, tokens
in/out, latency, parse success. Without this, quality regressions across 30 projects
are undiagnosable.

---

## Phase 5 — Extended Use Cases (Est. 1–2 days each)

All reuse the Phase 0–4 infrastructure. Each is a new MCP tool with a prompt template
and response parser.

### 5a — Test Optimization Based on Changes

**Trigger**: issue transitions to "In Progress" / "Resolved"
**Logic**: retrieve the changed issue's chunks → find related existing tests → ask
which need re-running and what new edge cases apply
**Tool**: `optimize_tests(issue_key, project_key)`

Materially better after Phase 2, since it can reason over real TestRail cases rather
than guessing what tests exist.

### 5b — KCD / Knowledge-Centered Documentation

**Trigger**: story marked "Done"
**Logic**: retrieve story + related resolved issues → generate a knowledge article
**Tool**: `generate_doc(issue_key, doc_type="kcd", project_key)`

Markdown sections: Summary, Implementation Details, Test Coverage, Known Issues /
Edge Cases, Lessons Learned.

### 5c — Defect Prediction from Historical Data

**Trigger**: new story or bug created
**Logic**: embed the new issue → find historically similar bugs → ask what defects
recurred, which areas are high risk, what to prioritize
**Tool**: `predict_risks(issue_key, project_key)`

Needs >50 historical issues to be meaningful. Validate against known outcomes before
anyone plans work around its output.

### 5d — Reusable Prompt Architecture

Each use case becomes a template in config:

```yaml
prompts:
  generate_tests:
    system: "You are an expert Test Engineer..."
    user: "Generate test cases for {issue_key}. Context: {context}"
    temperature: 0.3
    output_schema: test_cases_v1     # every template declares its parser contract
```

Bind each template to an output schema. Prompt and parser must version together —
drift between them is what produced the original paragraph-instead-of-rows bug.

---

## Summary Table

| Phase | What | Timeline | Dependencies |
|---|---|---|---|
| **0** | **Correctness & evaluation** | **2–3 days** | **None — start here** |
| 1 | RAG as MCP server (+ auth, health) | 1–2 days | Phase 0 |
| 2 | TestRail corpus + feedback loop | 2–3 days | Phase 0 |
| 3 | Multi-project support | 3–4 days | Phase 1 |
| 4 | Hosted shared deployment | 2–3 days | Phase 3 |
| 5a | Test optimization | 1–2 days | Phase 2 |
| 5b | KCD doc generation | 1–2 days | Phase 3 |
| 5c | Defect prediction | 1–2 days | Phase 3 + history |
| 5d | Prompt template system | 1 day | After 5a–5c |

**Total: ~14–21 days** to a full production system, depending on Phase 5 scope.

---

## Immediate Next Step

Run a Full Sync to rebuild the vector store with real embeddings, then start Phase 0:

```
backend/eval/
├── __init__.py
├── fixtures.py     # ~20 queries with expected issue keys
├── retrieval.py    # Recall@k, MRR, similarity floor
├── groundedness.py # do generated tests trace to retrieved chunks?
└── run.py          # prints a report; exits non-zero below threshold
```

Existing `backend/app/services/*` modules import directly — no duplication needed.
