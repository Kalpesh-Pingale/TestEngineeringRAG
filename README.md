# Test Engineering RAG Platform

An AI-powered Test Engineering Platform using **Jira** + **TestRail** + a local **vector database**, built to give test generation access to institutional testing knowledge — past issues, related defects, and (planned) previously accepted test cases.

> 📄 **New to this project?** [`docs/TECHNICAL_OVERVIEW.md`](docs/TECHNICAL_OVERVIEW.md) is a plain-language,
> team-shareable walkthrough of every tool in the stack — what it is, why it was picked over the obvious alternative,
> and an honest answer on whether RAG actually saves tokens here. Renders directly on GitHub/GitLab, including the
> architecture diagram. A styled HTML version with the same content is at
> [`docs/TECHNICAL_OVERVIEW.html`](docs/TECHNICAL_OVERVIEW.html) — open it in a browser.

## Architecture

```
┌──────────────────────┐
│      React UI        │
│  (Port 3000)         │
└──────────┬───────────┘
           │ REST APIs
┌──────────▼───────────┐
│   FastAPI Backend     │
│  (Port 8000)          │
└──────────┬───────────┘
           │
     ┌─────┼─────┐
     │     │     │
┌────▼┐ ┌──▼──┐ ┌▼────┐
│Jira │ │VecDB│ │TestR│
│REST │ │local│ │ API │
│/MCP │ │files│ │/MCP │
└──┬──┘ └──┬──┘ └──┬──┘
   │       │       │
   └───────┼───────┘
           │
    ┌──────▼─────────────┐
    │ Embeddings          │
    │ fastembed (ONNX)    │
    │ local, no server    │
    └──────┬─────────────┘
           │
    ┌──────▼──────┐
    │  Groq LLM   │
    └─────────────┘
```

## What This Does

1. **Ingests Jira data** — Reads User Stories and Bugs from a Jira project into a local vector store
2. **Incremental sync** — Subsequent runs process only changed issues, using timestamp + content-hash change detection
3. **Two-stage RAG test generation** — Fetches the target issue's chunks by exact key match, then retrieves semantically similar *other* issues as reference context, and sends both to the LLM with distinct roles
4. **TestRail upload** — Optionally uploads generated test cases
5. **Dashboard** — React UI showing sync status, vector DB contents, full RAG pipeline trace, and generated tests

### What RAG does and does not buy you

Be precise about this — the honest numbers matter more than the pitch.

Measured on a real Jira issue: raw Jira JSON is ~2,046 tokens, the *clean extracted text* is ~94 tokens, and the stored vector chunk is ~100 tokens. **Most of that 20× reduction is stripping the Jira JSON envelope, not retrieval** — a well-implemented MCP server that returns plain text achieves it without any vector database.

| Use case | Does RAG save tokens? |
|---|---|
| Generate tests for **one known issue** | **No** — RAG sends target + context chunks (~600 tok) where a clean single-issue fetch sends ~94 tok |
| Analysis needing **many issues** (defect prediction, regression selection, KCD) | **Yes, 20–600×** — and cross-project analysis (~1.2M tok raw) does not fit in context at all without it |
| **Aggregate statistics** ("which component has most defects") | **Neither** — top-k retrieval returns a biased sample. Compute these in code, not with an LLM |

The durable value is capability, not cost: semantic search across projects, historical defect context, and reuse of previously accepted test cases — none of which a per-request Jira fetch can do. Output tokens (generating the tests themselves) dominate total spend and are unaffected by retrieval.

## Project Structure

```
├── .gitignore
├── config.yaml             # ⚠️ NOT READ BY ANY CODE — aspirational only. All live config is in backend/.env
├── backend/
│   ├── .env                # ← the ONLY .env that is loaded
│   ├── .env.example        # template; copy to .env
│   ├── requirements.txt
│   ├── chromadb/           # vector store data (gitignored, rebuildable)
│   ├── model_cache/        # downloaded ONNX embedding model (gitignored)
│   └── app/
│       ├── main.py         # FastAPI entry point + /api/health diagnostics
│       ├── config.py       # Pydantic settings from backend/.env
│       ├── models/         # Pydantic data models
│       ├── routers/        # REST API endpoints
│       └── services/
│           ├── jira_service.py       # Jira data fetching (REST or MCP)
│           ├── chunker.py            # Text chunking
│           ├── embedding_service.py  # fastembed (local ONNX) — fails loudly
│           ├── vector_store.py       # numpy-backed store, metadata filtering
│           ├── sync_service.py       # Full/incremental sync engine
│           ├── rag_service.py        # Two-stage RAG pipeline
│           ├── test_generator.py     # JSON-first parsing of LLM output
│           ├── testrail_service.py   # Upload to TestRail
│           └── mcp_client.py         # MCP protocol client
├── prompt/
│   ├── prompt.md           # Original system specification (updated)
│   └── PROMPT_REVIEW.md    # Review of the spec: 12 gaps + severity
├── docs/
│   ├── TECHNICAL_OVERVIEW.md    # plain-language walkthrough of the stack
│   ├── TECHNICAL_OVERVIEW.html  # same content, styled for a browser
│   └── RAG_PRODUCTION_ROADMAP.md
└── frontend/
    ├── .env.example        # REACT_APP_API_URL — public values only
    ├── package.json
    ├── tailwind.config.js  # design tokens
    ├── postcss.config.js
    └── src/
        ├── index.css       # Tailwind + component classes
        ├── App.tsx         # sidebar shell + health indicator
        ├── api/client.ts   # typed API client; logs every RAG call
        ├── lib/ragLog.ts   # in-browser RAG activity log (session-scoped)
        └── components/
            ├── ui.tsx            # shared primitives (Card, Badge, StatCard…)
            ├── HealthPanel.tsx   # system diagnostics drawer
            ├── SyncDashboard.tsx
            ├── VectorExplorer.tsx
            ├── RAGExplorer.tsx
            ├── RAGLog.tsx        # activity log panel
            └── TestGeneration.tsx
```

## Prerequisites

| Component | Requirement | Notes |
|-----------|------------|-------|
| Python | 3.11+ | Tested on 3.14 |
| Node.js | 18+ | For React frontend |
| Jira | Cloud or Data Center | Account with API access |
| Groq API Key | Free tier available | Get key at console.groq.com |
| Embedding model | **Automatic** | `pip install -r requirements.txt` pulls `fastembed`; the ~90MB ONNX model downloads on first use. No server, no API key, no GPU |
| TestRail | *Optional* | Disable with `TESTRAIL_ENABLED=false` |
| MCP Servers | *Optional* | Set `JIRA_USE_MCP=false` to use the REST API directly |

> **Ollama is no longer used.** Earlier versions called Ollama for `nomic-embed-text` embeddings. That path required running a model server and silently produced meaningless vectors when unavailable — see [Embeddings](#embeddings-important) below.

## Quick Start

```bash
# 1. Backend dependencies
cd backend
pip install -r requirements.txt

# 2. Configure
cp .env.example .env     # then fill in Jira + Groq credentials

# 3. Run backend  (first start downloads the ~90MB embedding model)
uvicorn app.main:app --reload --port 8000

# 4. Frontend (separate terminal)
cd frontend
npm install
npm start
```

Backend API docs: http://localhost:8000/docs · UI: http://localhost:3000

**Verify setup before syncing** — the sidebar health indicator should read *"All systems ready"*. Click it for per-component diagnostics, or check directly:

```bash
curl -s http://localhost:8000/api/health
```

## Embeddings (important)

Embeddings are what make retrieval work. Getting them wrong degrades every result in a way that is invisible from the output.

- **Provider:** `fastembed` — ONNX runtime, no PyTorch, no server process, no API key, CPU-only
- **Default model:** `BAAI/bge-small-en-v1.5` (384 dimensions)
- **Failure policy:** embedding failure **raises**. The system never stores a placeholder vector

**Changing `EMBEDDING_MODEL` invalidates every stored vector.** Vectors from different models are not comparable — cosine similarity between them is meaningless. Every vector is stamped with the model that produced it, and on mismatch the app refuses to serve queries and tells you to run a Full Rebuild:

```
Vector store contains embeddings from ['fastembed:BAAI/bge-small-en-v1.5'] but the active
model is 'fastembed/other-model'. Similarity scores across different models are meaningless.
Run a Full Sync to rebuild the vector store.
```

## Configuration

All live configuration is in **`backend/.env`**. Copy `backend/.env.example` to start.

> ⚠️ A `.env` in the repository root is **not read by anything**. If one appears, it is a leftover — delete it, and never commit `.env` files (see [Secrets](#secrets)).

| Variable | Description | Example |
|----------|-------------|---------|
| **Jira** | | |
| `JIRA_BASE_URL` | Your Jira instance URL | `https://company.atlassian.net` |
| `JIRA_PROJECT_KEY` | Jira project key | `PROJ` |
| `JIRA_EMAIL` | Your Jira login email | `user@company.com` |
| `JIRA_API_TOKEN` | Jira API token | *(from id.atlassian.com/manage/api-tokens)* |
| `JIRA_MCP_SERVER` | Jira MCP server URL | `http://localhost:8080` |
| `JIRA_USE_MCP` | Use MCP vs REST API | `false` (REST is simpler to start with) |
| **TestRail** | | |
| `TESTRAIL_ENABLED` | Enable/disable TestRail upload | `false` to skip entirely |
| `TESTRAIL_BASE_URL` | TestRail instance URL | `https://company.testrail.io` |
| `TESTRAIL_PROJECT_ID` / `_SUITE_ID` / `_SECTION_ID` | Target location for new cases | `1` |
| `TESTRAIL_USERNAME` / `_API_KEY` | TestRail credentials | |
| **Embedding** | | |
| `EMBEDDING_PROVIDER` | Embedding backend | `fastembed` |
| `EMBEDDING_MODEL` | Model name — **changing this requires a Full Sync** | `BAAI/bge-small-en-v1.5` |
| `FASTEMBED_CACHE_DIR` | Where the ONNX model is cached | `./model_cache` |
| **LLM** | | |
| `LLM_PROVIDER` | LLM provider | `groq` |
| `LLM_MODEL` | Model for generation — must be a chat model your Groq key can access (`GET /openai/v1/models` lists them) | `openai/gpt-oss-120b` |
| `GROQ_API_KEY` | Your Groq API key | *(from console.groq.com)* |
| **Sync / retrieval** | | |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Chunking parameters | `800` / `150` |
| `TOP_K_RESULTS` | Context chunks retrieved from *other* issues | `5` |
| `ENABLE_INCREMENTAL_SYNC` | Enable incremental sync | `true` |

> `TOP_K_RESULTS` controls **context** retrieval only. The target issue's own chunks are always fetched in full by exact key match, so raising it does not make the issue under test more complete — it only adds more unrelated reference material.

### Using without TestRail

Set `TESTRAIL_ENABLED=false`. Test generation and the CSV export work normally; only the upload step is unavailable.

### Using without MCP servers

Set `JIRA_USE_MCP=false` to use the Jira REST API directly (needs `JIRA_EMAIL` + `JIRA_API_TOKEN`). This is the simplest way to get started; MCP is optional.

## Workflow

### 1. First run — Full Sync

Sync tab → **Full Rebuild**. Fetches all Stories and Bugs, chunks them, embeds locally, and writes `backend/chromadb/`. Each vector is stamped with the embedding model that produced it.

### 2. Ongoing — Incremental Sync

Sync tab → **Incremental Sync**. Fetches only issues updated since the last run; unchanged content (same hash) is skipped without re-embedding.

### 3. Generate test cases

Test Generation tab → enter an issue key (e.g. `PROJ-123`) → **Generate Tests**.

1. **Stage 1** — all chunks whose `issue_key` matches, by exact match. If the issue is not indexed, you get a clear `409` naming the indexed keys rather than tests generated from unrelated context
2. **Stage 2** — top-k semantically similar chunks from *other* issues, as labelled reference material
3. Both go to the LLM under distinct headings (`TARGET ISSUE` vs `REFERENCE ONLY`), with a strict JSON output contract
4. Results render one row per test case; export to CSV or upload to TestRail

### 4. RAG Explorer

Full pipeline trace for any query: retrieved chunks with similarity scores, the exact prompt sent, the raw response, and token usage. This is the first place to look when output quality is poor.

### 5. Activity Log

Below the trace, the **Activity Log** records every RAG call made in the session — query, semantic search, similarity search, and test generation, including the ones triggered from the Test Generation tab. Each entry carries the operation, wall-clock duration, chunks retrieved, best similarity score, tokens used, and — on failure — the backend's own message and status code.

The trace explains *one* result; the log shows the sequence, which is what you need when quality drifts between calls, one query is unexpectedly slow, or a request fails intermittently. It is logged in the API client (`api/client.ts`), so no call can bypass it.

Scope: the log lives in the browser, is capped at 100 entries, persists across reloads via `sessionStorage`, and is discarded when the tab closes. Nothing is sent anywhere, and it is separate from the backend's server-side logging (`LOG_LEVEL`).

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Per-component diagnostics (embeddings, vector store, LLM, Jira, TestRail) |
| POST | `/api/sync/full` | Full rebuild |
| POST | `/api/sync/incremental` | Incremental sync |
| GET | `/api/sync/status` | Current sync status |
| GET | `/api/sync/metadata` | Sync metadata incl. embedding version |
| GET | `/api/vector/stats` | Vector DB stats |
| GET | `/api/vector/documents` | All stored chunks + metadata |
| POST | `/api/vector/search` | Similarity search (no LLM call) |
| POST | `/api/rag/query` | RAG query |
| POST | `/api/rag/generate-tests` | Generate tests for an issue |
| POST | `/api/rag/similar` | Find similar issues |
| POST | `/api/rag/semantic-search` | Semantic search |
| POST | `/api/testrail/upload` | Upload test cases |
| POST | `/api/testrail/upload-generated` | Upload generated tests |
| GET | `/api/config/` | Current config |

**Status codes:** `409 Conflict` means a setup precondition failed — issue not synced, embedding model mismatch, missing API key. The `detail` field carries the fix. `500` means an unexpected error.

## Key Design Decisions

- **Two-stage retrieval.** The target issue is fetched by exact metadata match, never by similarity. Pure top-k gives no guarantee the issue you asked about ranks in the top-k — it competes with every other issue, so the one document that must be present can be missing.
- **Embedding failure is fatal.** No placeholder vectors, ever. A hash-based stand-in is indistinguishable from a real vector once stored and silently degrades retrieval to random selection with no error and no metric.
- **Embedding version stamping.** Every vector records its model; a mismatch blocks queries instead of returning meaningless similarity scores.
- **Strict JSON output contract.** The LLM returns a JSON array parsed with `json.loads`; a prose parser remains only as a fallback. Reconstructing records from prose with regex collapses every test case into one paragraph when formatting drifts.
- **Retrieved content is data, never instructions.** Jira descriptions are user-authored and untrusted — anyone who can file a ticket could otherwise inject directives into the prompt.
- **File-based vector store.** `vectors.npy` + `metadata.jsonl`, written once per sync rather than once per chunk. Benchmarked at 1,800 chunks: 2.8 MB, 2.3 ms/query — no external database needed well past 10k chunks.
- **Honest token accounting.** `baseline_tokens` / `retrieved_tokens` / `tokens_saved` are reported per call. Savings are legitimately zero when the corpus is smaller than `top_k`, and the API says so rather than manufacturing a number.

## Secrets

Four values in this project are real credentials: `JIRA_API_TOKEN`, `GROQ_API_KEY`, `TESTRAIL_API_KEY`, and the account identifiers next to them (`JIRA_EMAIL`, `TESTRAIL_USERNAME`).

**The rules that keep them safe:**

| Rule | Why |
|---|---|
| Secrets live **only** in `backend/.env`, which is gitignored | One file, one place to rotate, nothing tracked by git |
| `backend/.env.example` holds **key names and dummy values**, and is committed | New contributors learn the shape of the config without ever seeing a real token |
| `frontend/.env.example` holds only **public** values | CRA inlines `REACT_APP_*` into the JS bundle at build time — anything there ships to the browser. Never put a token in it |
| In production, secrets come from the **host's environment-variable store**, never from a file in the repo | See [Deployment](#deployment) |
| A leaked key is rotated, not un-pushed | Git history is permanent; `git push --force` does not delete a key someone already scraped |

**Before your first push**, confirm nothing sensitive is staged:

```bash
git init
git add -A
git status --short          # no .env, no .venv/, no node_modules/, no chromadb/, no model_cache/
git ls-files | grep -i env  # should list ONLY the two .env.example files
```

If a secret was already committed at some point: **rotate the key at the provider first** ([Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens), [Groq console](https://console.groq.com), TestRail → My Settings → API Keys), then clean history. Rotation is the fix; history rewriting is only cleanup.

### Where secrets are read from

`backend/app/config.py` loads `backend/.env` with `override=True` when the file exists, then falls back to Pydantic settings, which read **process environment variables**. That fallback is exactly what makes cloud deployment work: on a host there is no `.env` file, and the platform's injected environment variables are picked up automatically. Nothing in the code changes between local and production.

## Deployment

### What can and cannot run on Vercel

Vercel functions are **serverless**: a read-only filesystem apart from an ephemeral `/tmp`, a bundle size cap, and a request timeout measured in seconds. Three parts of this backend conflict with that model:

| Feature | Conflict with Vercel serverless |
|---|---|
| File-based vector store (`backend/chromadb/vectors.npy`) | The filesystem is read-only, and `/tmp` is discarded between invocations — a Full Sync would write vectors that vanish before the next request |
| `fastembed` ONNX embeddings | `onnxruntime` plus the ~90MB model download is heavy for a serverless bundle and re-downloads on every cold start |
| Full/incremental sync over a whole Jira project | Minutes of work against a function timeout |

**So: deploy the frontend on Vercel, and the backend on a host with a persistent disk and long-running processes** (Render, Railway, Fly.io, or any VM/container). This is the least-effort path and needs no code changes.

[`render.yaml`](render.yaml) in the repo root is a ready-made blueprint for the backend half: **Render → New → Blueprint → pick this repo**. It sets the root directory, build and start commands, the health check, and every non-secret variable; the secrets (`sync: false`) are prompted for in the dashboard.

It targets Render's **free** plan, which has no persistent disk and sleeps after ~15 minutes idle — so after each wake the ONNX model re-downloads and the vector store is empty until a Full Sync is re-run. The vector store is rebuildable by design, so this costs time rather than data. For persistence, set `plan: starter`, add a `disk:` block mounted at `/var/data`, and point `CHROMA_DB_PATH` and `FASTEMBED_CACHE_DIR` at it.

If the backend *must* be on Vercel, the vector store has to move to a hosted vector database (Qdrant Cloud, Pinecone, Supabase pgvector) and embeddings to a hosted API, with sync driven by a cron job rather than a request. That is a real rewrite of `vector_store.py` and `embedding_service.py`, not a config change.

### Frontend on Vercel

1. Push this repo to GitHub, then **Add New → Project** in Vercel and import it.
2. Set **Root Directory** to `frontend`. Vercel then auto-detects Create React App (build `npm run build`, output `build`).
3. Add one environment variable (below), pointing at wherever the backend is hosted.
4. Deploy. Every push to the default branch redeploys; every PR gets a preview URL.

### Environment variables on Vercel

Vercel does not read `.env` files from the repo — that is the point of gitignoring them. You provide values in **Project → Settings → Environment Variables**, and Vercel injects them into the build and the runtime. Each variable is scoped to one or more of **Production**, **Preview**, and **Development**, so a preview deployment can point at a staging backend.

**Frontend project:**

| Variable | Value | Scope |
|---|---|---|
| `REACT_APP_API_URL` | `https://your-backend-host.example.com` | Production, Preview |

> `REACT_APP_*` values are **baked into the built JavaScript** and are public. This one is just a URL, which is fine. Never add `GROQ_API_KEY` or a Jira token to the frontend project.

**Backend host** (Render/Railway/Fly/Vercel-Python alike) — set every key from `backend/.env.example` in that platform's environment settings, and mark the tokens as secret/sensitive where the platform offers it:

```
JIRA_BASE_URL, JIRA_PROJECT_KEY, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_USE_MCP=false
TESTRAIL_ENABLED, TESTRAIL_BASE_URL, TESTRAIL_PROJECT_ID, TESTRAIL_SUITE_ID,
TESTRAIL_SECTION_ID, TESTRAIL_USERNAME, TESTRAIL_API_KEY
EMBEDDING_PROVIDER, EMBEDDING_MODEL, FASTEMBED_CACHE_DIR
LLM_PROVIDER, LLM_MODEL, GROQ_API_KEY
CHUNK_SIZE, CHUNK_OVERLAP, TOP_K_RESULTS, ENABLE_INCREMENTAL_SYNC, LOG_LEVEL
CORS_ORIGINS=https://your-frontend.vercel.app
```

`CORS_ORIGINS` must include the deployed frontend origin (comma-separated for several) or the browser blocks every API call. `CHROMA_DB_PATH` and `FASTEMBED_CACHE_DIR` should point at a **mounted persistent volume** so vectors and the ONNX model survive restarts.

Managing Vercel variables from the CLI, if you prefer it to the dashboard:

```bash
npm i -g vercel
vercel link
vercel env add REACT_APP_API_URL production   # prompts for the value; never echoed into a file
vercel env pull .env.local                    # writes a local copy — already gitignored
```

### Deployment checklist

- [ ] `git status --short` shows no `.env`, `.venv/`, `node_modules/`, `chromadb/`, or `model_cache/`
- [ ] `GROQ_API_KEY` / `JIRA_API_TOKEN` / `TESTRAIL_API_KEY` set on the backend host, not in any committed file
- [ ] `CORS_ORIGINS` on the backend includes the Vercel frontend URL
- [ ] `REACT_APP_API_URL` on Vercel points at the deployed backend (https, no trailing slash)
- [ ] Backend has a persistent volume mounted for `CHROMA_DB_PATH` and `FASTEMBED_CACHE_DIR`
- [ ] Full Sync run once against the deployed backend, then `/api/health` reads ready

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Sidebar shows **"Setup required"** | A dependency isn't ready | Click it for per-component detail and the exact remedy |
| `409: Vector store contains embeddings from [...]` | `EMBEDDING_MODEL` changed since last sync | Run **Full Rebuild** |
| `409: Issue 'X' is not in the vector store` | Issue not synced (or wrong key) | Run a sync; the message lists indexed keys |
| `409: fastembed is not installed` | Missing dependency | `pip install -r requirements.txt` |
| `409: GROQ_API_KEY is not configured` | Missing key | Set it in `backend/.env` |
| Generated tests look irrelevant | Retrieval problem, not a prompt problem | Open **RAG Explorer** and check similarity scores. Below ~0.45 usually means nothing relevant is indexed |
| Backend unreachable from UI | API not running | `uvicorn app.main:app --reload --port 8000` from `backend/` |
| First start is slow | One-time ONNX model download (~90MB) | Cached in `backend/model_cache/` afterwards |

## FAQ

**Do I need Ollama?**
No. Embeddings run locally via `fastembed` (ONNX, CPU). Nothing to install or run beyond `pip install`.

**Do I need MCP servers?**
No. Set `JIRA_USE_MCP=false` to use the Jira REST API directly.

**Can I use it without TestRail?**
Yes. Set `TESTRAIL_ENABLED=false`.

**Can I change the embedding model?**
Yes, but it invalidates every stored vector. The app detects the mismatch and requires a Full Rebuild before serving queries.

**Does this actually save tokens?**
For multi-issue analysis, substantially. For generating tests on a single known issue, no — see [What RAG does and does not buy you](#what-rag-does-and-does-not-buy-you). Measure with the `tokens_saved` / `baseline_tokens` fields rather than assuming.

**Can I raise `TOP_K_RESULTS` to make defect analysis accurate?**
No. Top-k retrieval selects by similarity to the query, so counting the selection reflects the query rather than your defect history — and the answer changes with the wording. Compute aggregate statistics in code over the stored metadata; use retrieval only for similarity.

**Is `config.yaml` used?**
No. No code reads it and PyYAML is not a dependency. All live configuration is in `backend/.env`.

**Where is data stored?**
`backend/chromadb/` (`vectors.npy`, `metadata.jsonl`, `sync_metadata.json`). Both it and `backend/model_cache/` are gitignored and rebuildable via Full Sync.

**Can I deploy the whole thing to Vercel?**
The frontend, yes. The backend, not as it stands — it writes the vector store to disk, downloads a ~90MB ONNX model, and runs multi-minute syncs, none of which fit serverless. Host the backend where it has a persistent disk and put `REACT_APP_API_URL` in the Vercel project. See [Deployment](#deployment).

**How do my API keys get to production if `.env` is gitignored?**
Through the host's environment-variable store (Vercel: Project → Settings → Environment Variables). `backend/app/config.py` falls back to process environment variables when no `.env` file is present, so the same code reads local files in development and injected variables in production. See [Secrets](#secrets).

**Can I use this for multiple Jira projects?**
Today it is single-project — change `JIRA_PROJECT_KEY` and re-sync. Multi-project isolation is Phase 3 in [docs/RAG_PRODUCTION_ROADMAP.md](docs/RAG_PRODUCTION_ROADMAP.md).

---

Built by **Kalpesh Pingale**.
