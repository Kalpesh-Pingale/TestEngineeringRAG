# Test Engineering RAG Platform — Setup & Run Instructions

## Prerequisites Checklist

| # | Item | Status |
|---|------|--------|
| 1 | Python 3.11+ installed | ✅ |
| 2 | Node.js 18+ installed | Check with `node --version` |
| 3 | Access to a Jira project | You need Jira URL + credentials |
| 4 | Groq API key (free) | Sign up at https://console.groq.com |
| 5 | Jira MCP Server or REST API | See section below |
| 6 | TestRail MCP Server (optional) | Set `TESTRAIL_ENABLED=false` if not using |
| 7 | Embedding model | Automatic — `pip install -r requirements.txt` pulls `fastembed`; the ~90MB ONNX model downloads on first use. No server, no API key, no GPU. |

> **Embeddings are not optional.** They are what makes retrieval work. If the model
> cannot load, the app now fails loudly with the fix in the message rather than
> storing meaningless vectors — check the health indicator in the sidebar.

---

## Step 1: Update `.env` File

Copy the template and fill it in:

```bash
cd backend
cp .env.example .env
```

> ⚠️ **`backend/.env` is the only `.env` that is loaded.** A `.env` in the repository
> root is ignored by the application — if one appears it is a leftover from an earlier
> version. Delete it rather than editing it, and never commit either file.
> (The stale root `.env` that shipped with earlier checkouts has been removed.)

> 🔑 **Credential hygiene.** `.env` holds a live Jira API token and Groq key in
> plaintext. `.gitignore` excludes every `.env` variant, but that only protects commits
> made *from now on*. Before this repository is pushed, shared, or made public,
> rotate both credentials:
> - Jira: revoke and reissue at https://id.atlassian.com/manage-profile/security/api-tokens
> - Groq: revoke and reissue at https://console.groq.com/keys
>
> Then update `backend/.env` only. For the full policy — what is committed, what is
> not, and how credentials reach a deployed environment — see
> [Secrets](README.md#secrets) in the README.

Update the following **required** values:

```
# === YOU MUST UPDATE THESE ===

JIRA_BASE_URL=https://your-company.atlassian.net     → your Jira instance URL
JIRA_PROJECT_KEY=ABC                                  → your Jira project key (e.g., MYPROJ)
JIRA_EMAIL=your-email@example.com                     → your Jira login email
JIRA_API_TOKEN=your-api-token                         → generate from id.atlassian.com/manage/api-tokens

GROQ_API_KEY=your-groq-api-key                        → from console.groq.com

# === OPTIONAL — only if using TestRail ===

TESTRAIL_ENABLED=false                                → set to true if you have TestRail
TESTRAIL_BASE_URL=https://company.testrail.io          → your TestRail URL
TESTRAIL_PROJECT_ID=1                                  → your TestRail project ID
TESTRAIL_USERNAME=your-email@example.com               → TestRail login
TESTRAIL_API_KEY=your-api-key                          → TestRail API key
```

### Configuration Reference

| Variable | What it does | Required? |
|----------|-------------|-----------|
| `JIRA_BASE_URL` | Your Jira instance URL | ✅ Yes |
| `JIRA_PROJECT_KEY` | The Jira project to sync | ✅ Yes |
| `JIRA_EMAIL` | Your Jira login email | ✅ Yes |
| `JIRA_API_TOKEN` | Jira API token (generate from Atlassian) | ✅ Yes |
| `JIRA_MCP_SERVER` | URL where Jira MCP server runs | Only if `JIRA_USE_MCP=true` |
| `JIRA_USE_MCP` | `true` = use MCP server, `false` = direct REST | Recommended `true` |
| `TESTRAIL_ENABLED` | `false` = skip TestRail entirely | No (default `false`) |
| `TESTRAIL_BASE_URL` | TestRail instance URL | Only if enabling TestRail |
| `TESTRAIL_PROJECT_ID` | TestRail project ID | Only if enabling TestRail |
| `TESTRAIL_SECTION_ID` | Section where test cases go | Only if enabling TestRail |
| `TESTRAIL_MCP_SERVER` | URL where TestRail MCP runs | Only if enabling TestRail |
| `GROQ_API_KEY` | Groq API key for LLM calls | ✅ Yes |
| `CHUNK_SIZE` | Text chunk size for embedding (default 800) | No |
| `TOP_K_RESULTS` | Number of chunks to retrieve (default 5) | No |
| `EMBEDDING_PROVIDER` | `fastembed` — local ONNX, no server needed | No |
| `EMBEDDING_MODEL` | Default `BAAI/bge-small-en-v1.5` (384-dim). **Changing this invalidates every stored vector** — the app detects the mismatch and requires a Full Sync | No |
| `FASTEMBED_CACHE_DIR` | Where the ONNX model is cached (default `./model_cache`) | No |
| `LLM_MODEL` | Groq model for generation (default `openai/gpt-oss-120b`). Groq retires models periodically — a `404 model_not_found` means the ID is gone; list current ones with `GET https://api.groq.com/openai/v1/models` | No |
| `CORS_ORIGINS` | Comma-separated origins allowed to call the API (default `http://localhost:3000`) | Only when the frontend is not on localhost:3000 |

---

## Step 2: Install Backend Dependencies

Open a terminal in the `backend` folder:

```bash
cd backend
pip install -r requirements.txt
```

This installs `fastembed`, which provides local embeddings via ONNX — no model
server, no API key, and no GPU. The ~90MB embedding model itself downloads on
first use and is cached in `backend/model_cache/`.

---

## Step 3: Install Frontend Dependencies

Open a terminal in the `frontend` folder:

```bash
cd frontend
npm install
```

No frontend configuration is needed for local development — the API client falls back
to `http://localhost:8000`. To point it elsewhere, copy the template and set the URL:

```bash
cp .env.example .env.local     # gitignored
```

```
REACT_APP_API_URL=http://localhost:8000
```

> ⚠️ Create React App **inlines every `REACT_APP_*` value into the JavaScript bundle**
> at build time. Whatever you put there is public. API tokens belong in
> `backend/.env` only — never in a frontend env file.

---

## Step 4: Start the Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Verify it's running: Open http://localhost:8000/docs — you should see the Swagger UI with all API endpoints.

**Then verify every dependency is actually ready** — this catches misconfiguration
*before* it silently degrades your results:

```bash
curl -s http://localhost:8000/api/health
```

`"status": "ok"` means embeddings, the vector store, and the LLM are all usable.
`"degraded"` means at least one required component needs setup — each entry carries
an `error` and a `fix`. The first call may take ~30s while the embedding model
downloads.

**If you see only 1 endpoint (`/api/health`)** and the rest are missing:
- Make sure your typing is correct — the backend needs `from pydantic import BaseModel` imported properly
- Run `python -c "from app.main import app; print(len(app.router.routes))"` to check routes loaded
- The most common cause is a silent import error in one of the router files

---

## Step 5: Start the Frontend

In a **separate terminal**:

```bash
cd frontend
npm start
```

Opens at http://localhost:3000

---

## Step 6: Run Initial Sync

1. Open the UI at http://localhost:3000
2. Check the sidebar health indicator reads **"All systems ready"** (click it for details)
3. Go to the **Sync** tab
4. Click **Full Rebuild**
5. Wait for completion — this fetches all Stories and Bugs from Jira, embeds them
   locally, and writes `backend/chromadb/`

Thereafter use **Incremental Sync**, which only reprocesses issues whose content
changed. Use **Full Rebuild** again only after changing `EMBEDDING_MODEL`.

---

## Using Without TestRail (Generate Tests Only)

The UI always shows the **Generate Tests** tab and the **Upload to TestRail** button. Here's what's possible:

| Action | TestRail Enabled | TestRail Disabled |
|--------|-----------------|-------------------|
| Generate test cases from Jira story | ✅ Always works | ✅ Always works |
| View generated tests | ✅ | ✅ |
| Upload to TestRail | ✅ Works | ❌ "Upload" button still shows but API call will fail |
| Copy/manually save test cases | ✅ | ✅ |

If you set `TESTRAIL_ENABLED=false`, the backend won't even attempt TestRail connections at startup. You can still generate tests — just skip the upload step.

To completely hide TestRail: Don't start the TestRail MCP server.

---

## Jira MCP Server — What It Is & How to Set Up

### What is an MCP Server?

MCP (Model Context Protocol) is a standard that lets apps talk to external systems through a local HTTP server. Instead of the backend talking directly to Jira's REST API, it talks to the Jira MCP server, which handles all the Jira complexity.

### Do I need one?

**Recommended** but not required. If you can't run an MCP server, set:

```
JIRA_USE_MCP=false
```

The backend will fall back to Jira REST API using your `JIRA_EMAIL` + `JIRA_API_TOKEN`.

### How to run the Jira MCP Server

The Jira MCP server is a separate Node.js process. It does **not** start automatically.

```bash
# Install and run (one command)
npx @anthropic-ai/mcp-jira --port 8080

# Or install globally first
npm install -g @anthropic-ai/mcp-jira
mcp-jira --port 8080
```

Once running, you should see something like:
```
Jira MCP server running on http://localhost:8080
```

Then update `.env`:
```
JIRA_MCP_SERVER=http://localhost:8080
JIRA_USE_MCP=true
```

### TestRail MCP Server (optional)

Same concept — only needed if `TESTRAIL_ENABLED=true`:

```bash
npx @anthropic-ai/mcp-testrail --port 8090
```

---

## How to Generate Test Cases (Without TestRail)

The simplest workflow to just generate test cases:

1. Ensure `.env` has valid Jira and Groq values
2. Run `uvicorn app.main:app` (backend)
3. Run `npm start` (frontend)
4. Go to **Sync** tab → **Full Sync** (index Jira data)
5. Go to **Test Generation** tab
6. Enter a Jira issue key (e.g., `PROJ-42`) → **Generate Tests**
7. Review the generated test cases in the UI

You can also use the API directly:

```bash
curl -X POST http://localhost:8000/api/rag/generate-tests \
  -H "Content-Type: application/json" \
  -d '{"issue_key": "PROJ-42"}'
```

---

## Folder Structure After Sync

After running a sync, you'll see:

```
chromadb/
├── vectors.npy        # Vector embeddings (numpy array)
├── metadata.jsonl     # Metadata for each vector
└── sync_metadata.json # Sync state (last sync time, hashes)
```

This is your local vector database. Delete it to reset and re-sync.

---

## Pushing to GitHub

Only source code, the two `.env.example` templates, and documentation are tracked.
Everything else — secrets, virtualenvs, dependencies, generated data, editor and
agent state — is ignored:

| Ignored | Why |
|---|---|
| `.env`, `.env.*`, `*.env` (except `*.env.example`) | Live credentials |
| `.venv/`, `node_modules/` | Reinstallable from `requirements.txt` / `package.json` |
| `backend/chromadb/` | Vector store — rebuild with a Full Sync |
| `backend/model_cache/` | ~90MB ONNX model — refetched on demand |
| `frontend/build/` | Build output |
| `.claude/`, `.commandcode/`, `.vscode/`, `.idea/` | Local tooling and editor state |
| `*.log`, `.vercel` | Scratch and deploy state |

Verify before the first push:

```bash
git init
git add -A
git status --short            # no .env, .venv/, node_modules/, chromadb/, model_cache/
git ls-files | grep -i env    # should list ONLY the two .env.example files
```

If a key was ever committed, **rotate it at the provider** — rewriting history does
not un-leak a token that was already public.

---

## Deploying

Short version: **frontend on Vercel, backend on a host with a persistent disk**
(Render, Railway, Fly.io, or a container/VM).

The backend cannot run on Vercel's serverless runtime as written — it writes the
vector store to disk, downloads a ~90MB ONNX model on first use, and runs syncs that
take minutes. Serverless gives a read-only filesystem, an ephemeral `/tmp`, and a
timeout measured in seconds.

Two settings connect the halves:

| Where | Variable | Value |
|---|---|---|
| Vercel (frontend project) | `REACT_APP_API_URL` | `https://your-backend-host.example.com` |
| Backend host | `CORS_ORIGINS` | `https://your-frontend.vercel.app` |

Credentials are set in the host's environment-variable store, not in a file.
`backend/app/config.py` loads `backend/.env` only when that file exists and otherwise
reads process environment variables — so the same code works locally and deployed,
with no changes.

Full walkthrough, the complete variable list, and a pre-deploy checklist:
[Deployment](README.md#deployment) in the README.

---

## Quick Reference — Key Endpoints

| What | URL | Method |
|------|-----|--------|
| API docs | http://localhost:8000/docs | GET |
| Health check | http://localhost:8000/api/health | GET |
| Full sync | http://localhost:8000/api/sync/full | POST |
| Generate tests | http://localhost:8000/api/rag/generate-tests | POST |
| RAG query | http://localhost:8000/api/rag/query | POST |
| Similarity search | http://localhost:8000/api/vector/search | POST |

---

## Troubleshooting

**Start here:** open http://localhost:8000/api/health (or click the sidebar health
indicator in the UI). Every required component reports `ready`, and anything that
isn't carries the specific remedy. Most issues below are diagnosable from it.

### Setup errors (HTTP 409)

A `409` means a precondition failed — it is your setup, not a crash, and the
`detail` field states the fix.

**"Vector store contains embeddings from [...] but the active model is [...]"**
→ `EMBEDDING_MODEL` changed since the last sync. Vectors from different models are
not comparable, so queries are blocked deliberately. Run **Full Rebuild**.

**"Issue 'PROJ-123' is not in the vector store"**
→ That issue hasn't been synced. Run a sync; the error lists the indexed keys so you
can confirm the key is right.

**"fastembed is not installed"**
→ `pip install -r requirements.txt` from `backend/`.

**"Failed to load embedding model '<name>'"**
→ Bad `EMBEDDING_MODEL` name, or no network access for the first-time download.
Check the name against `TextEmbedding.list_supported_models()`.

**"GROQ_API_KEY is not configured"**
→ Set it in `backend/.env`.

**"Vector store is empty. Run a Full Sync before querying."**
→ Exactly what it says — sync first.

### Other issues

**"No module named app"**
→ Run uvicorn from the `backend/` directory.

**Frontend shows "Cannot reach the backend"**
→ Backend isn't running on port 8000, or another process already owns that port.
On Windows: `netstat -ano | findstr :8000`. If the frontend is deployed, check
`REACT_APP_API_URL` — it is baked in at **build** time, so changing it requires a
rebuild, not just a restart.

**Browser console shows a CORS error**
→ `CORS_ORIGINS` on the backend must include the exact frontend origin (scheme, host,
port; no trailing slash), comma-separated for several. Restart the backend after
changing it.

**Config changes seem to have no effect**
→ You may be editing the wrong file. Only `backend/.env` is loaded; a root `.env`
is ignored. Restart uvicorn after editing.

**Sync shows 0 issues**
→ Check Jira credentials and project key. Try `JIRA_USE_MCP=false` as a fallback.

**"Cannot find MCP server"**
→ MCP server isn't running. Start it, or set `JIRA_USE_MCP=false` to use the REST API.

**TestRail upload fails**
→ Likely `TESTRAIL_ENABLED=false` or the TestRail MCP server isn't running. Test
generation and CSV export work regardless.

**Generated tests are irrelevant or generic**
→ This is almost always retrieval, not prompting. Open **RAG Explorer**, run the
query, and check the similarity scores on the retrieved chunks. Scores below ~0.45
usually mean nothing relevant is indexed for that topic.

**A call failed and the error message is already gone**
→ The **Activity Log** at the bottom of **RAG Explorer** keeps every RAG call made
this session — operation, duration, chunks retrieved, best similarity score, tokens,
and the backend's message and status code on failure. It covers calls made from the
Test Generation tab too. It is browser-side and session-scoped; nothing is uploaded.

**First backend start hangs for ~30 seconds**
→ One-time ONNX embedding-model download. Cached in `backend/model_cache/` afterwards.

---

Built by **Kalpesh Pingale**.
