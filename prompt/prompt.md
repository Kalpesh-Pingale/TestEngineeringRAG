AI Test Engineering RAG Platform using Jira MCP + TestRail MCP + Vector Database
I want you to create an AI-powered Test Engineering Platform that demonstrates how a production-ready Retrieval Augmented Generation (RAG) architecture can reduce LLM token consumption while supporting automated software testing.
The application should be built using React for the frontend and Python (FastAPI) for the backend.
The application should use Jira as the primary data source and TestRail as the destination for generated test cases.
The overall objective is to ingest Jira project data into a Vector Database only once, continuously synchronize only changed Jira artifacts, and use Retrieval Augmented Generation (RAG) for generating high-quality test cases with minimal token usage.

High Level Architecture
                   +----------------------+
                    |      React UI        |
                    +----------+-----------+
                               |
                               |
                     REST / WebSocket APIs
                               |
                               |
                  +------------v-------------+
                  |     FastAPI Backend      |
                  +------------+-------------+
                               |
          --------------------------------------------
          |                    |                      |
          |                    |                      |
          v                    v                      v

   Jira MCP Server      ChromaDB / Vector DB     TestRail MCP Server
          |                    |                      |
          |                    |                      |
          -------------------------------
                     |
               Embedding Model
               (fastembed / BAAI/bge-small-en-v1.5,
                local ONNX — no server, no API key)

                     |
                     v

               Groq LLM (llama-3.3-70b-versatile)


Functional Requirements
1. Jira Data Ingestion
The application should connect to a specific Jira project and retrieve:
User Stories
Bugs
Tasks (optional)
Epics (optional)
Acceptance Criteria
Description
Labels
Components
Priority
Status
Sprint
Linked Issues
Attachments metadata (optional)
Comments (configurable)
using either:
Jira MCP Server (preferred)

2. Data Preprocessing
Each Jira issue should be converted into a structured document.
Example metadata:
Issue Key
Project Key
Issue Type
Summary
Description
Acceptance Criteria
Priority
Status
Sprint
Labels
Components
Story Points
Created Date
Updated Date
Reporter
Assignee

Create semantic chunks suitable for embedding.
Chunk size should be configurable.

CHUNKING MUST BE FIELD-AWARE
Do not concatenate all fields into one blob and split every N characters.
Doing so splits acceptance criteria mid-list and merges them with unrelated
comment text.

Instead:
- Chunk per field (description / acceptance criteria / comments).
- Prefix EVERY chunk with "{issue_key}: {summary}" so each chunk is
  independently meaningful. Otherwise only the first chunk carries the issue
  identity and later chunks embed as anonymous fragments that retrieve poorly.
- Most Jira issues fit in one or two chunks; do not over-split.

3. Embedding Generation
Generate embeddings locally using fastembed (ONNX runtime).
Default model: BAAI/bge-small-en-v1.5 (384-dim).
No model server, no API key, no GPU, ~90MB one-time download.

Rationale: an embedding model that requires running a separate server
(e.g. Nomic Embed via Ollama) is a deployment dependency, not a config value.
On hardware that cannot run one, the requirement is unmeetable.

FAILURE POLICY (mandatory)
Embedding failure is FATAL and must raise. Never persist a vector that did
not come from the configured model. Specifically: no hash-based or random
"fallback" vectors. Such a vector has no semantic meaning, is indistinguishable
from a real one once stored, and silently degrades retrieval to random
selection with no error and no metric — the only symptom is poor output.

Store embeddings in local ChromaDB-compatible storage.
Each embedding must carry metadata including:
Issue Key
Project Key
Issue Type
Updated Timestamp
Embedding Version   <- "{provider}:{model}", stamped on every vector
Vector ID
Hash

EMBEDDING MIGRATION
Vectors produced by different models are not comparable; cosine similarity
between them is meaningless. On startup, compare every stored vector's
embedding_version against the active model. On mismatch, block RAG queries
and require a Full Sync, surfacing the reason in the UI. A dimension mismatch
must raise rather than return a ranking.


4. Initial Full Synchronization
On first execution:
Read every User Story and Bug from the configured Jira project.
Generate embeddings.
Store all embeddings in ChromaDB.
Save synchronization metadata.
Display ingestion progress.

5. Incremental Synchronization (Change Detection)
Subsequent executions should NOT reload the entire Jira project.
Implement incremental synchronization using change detection.
Supported strategies:
Timestamp-Based
Retrieve only issues updated after:
lastSyncTime

Example JQL:
project = ABC
AND updated >= "lastSyncTime"


Hash-Based Detection
For every Jira issue:
Generate a content hash.
If:
Existing Hash == New Hash

Skip embedding generation.

Else:
Update embedding.


Newly Created Issues
Automatically detect:
New User Stories
New Bugs
Generate embeddings only for newly added issues.

Deleted Issues
If an issue no longer exists:
Remove corresponding vectors from ChromaDB.

Synchronization Dashboard
Display:
New Issues
Updated Issues
Deleted Issues
Skipped Issues
Total Tokens Saved
Last Synchronization Time

6. Retrieval Augmented Generation (RAG)
When the user submits a request such as:
Generate test cases for Story ABC-123

Retrieval is TWO-STAGE, and stage 1 must be deterministic:

Stage 1 — Target retrieval (exact match, not similarity)
Fetch every chunk whose issue_key metadata equals the requested key.
Do NOT rely on similarity search for this. Top-k ranking gives no guarantee
that the requested issue appears at all — it competes with every other issue
in the store — so the one document that must be in context can be missing.
If the issue is not indexed, fail with an actionable error naming the
indexed keys. Never silently generate from unrelated context.

Stage 2 — Context retrieval (semantic top-k)
Retrieve top 5-10 chunks from OTHER issues, seeded by the target issue's text.
These supply historical patterns, prior defects, and house style.

The prompt must label the two sets differently:
  TARGET ISSUE   -> the specification under test; write test cases for this only.
  REFERENCE ONLY -> related past issues; inform coverage, never generate tests for them.

Display both sets, with similarity scores, in the RAG Explorer.

Token accounting must be defined explicitly and reported honestly:
  baseline_tokens  = cost of stuffing ALL indexed content into the prompt
  retrieved_tokens = cost of the context actually sent
  tokens_saved     = max(0, baseline - retrieved)
Savings are legitimately zero when the corpus is smaller than top_k. Report
that rather than manufacturing a number.

Security: retrieved Jira content is untrusted user input. Anyone who can file
a ticket can write instructions into a description. The prompt must state that
context is data and never instructions, delimit it clearly, and neutralize
fence sequences in retrieved text.

7. Test Case Generation

OUTPUT FORMAT CONTRACT (mandatory)
The LLM must return ONLY a JSON array — no markdown fences, no prose before
or after. Parse it with json.loads. Keep a prose parser as a fallback only.

Asking for prose and reconstructing records from it with regex is not viable:
formatting drifts between calls, and when it does, every test case collapses
into a single record with the whole response dumped into one field.

Each array element must be an object with exactly these keys:
  "title"                 string  - specific and action-oriented
  "preconditions"         string  - required state, "" if none
  "steps"                 array of strings - ONE action per element
  "expected_results"      string  - the observable outcome
  "priority"              "High" | "Medium" | "Low"
  "test_type"             "Positive" | "Negative" | "Boundary Value" | "Edge Case"
                          | "API" | "UI" | "Regression" | "Exploratory" | "Non-functional"
  "automation_candidate"  "Yes" | "No"

Reject and surface an error if zero cases parse — never render an empty table
as if it were a successful generation.

The platform should support generating:
Manual Test Cases
Positive Test Cases
Negative Test Cases
Boundary Value Test Cases
Exploratory Test Ideas
API Test Scenarios
UI Test Scenarios
Regression Test Cases
Edge Cases
Non-functional Test Suggestions
Each generated test case should include:
Title
Preconditions
Test Steps
Expected Results
Priority
Test Type
Automation Candidate (Yes/No)
Requirement/User Story Mapping
Traceability to Jira Issue

8. Upload Test Cases to TestRail
After generation:
Upload test cases automatically to the configured TestRail project using the TestRail MCP Server.
The workflow should:
Identify the target TestRail Project.
Identify the Section.
Create Test Cases.
Map the Jira Issue Key to the TestRail reference field.
Return created TestRail IDs.
Display upload status in the UI.

9. AI Knowledge Improvement Using RAG
As the vector database grows, the platform should leverage previously ingested data
to improve retrieval quality.
Support:
Semantic search
Similar story detection
Similar bug detection
Duplicate story suggestions
Historical context retrieval
Reuse of existing testing knowledge

INDEX EXISTING TESTRAIL CASES, NOT ONLY JIRA
The highest-value historical corpus for generating test cases is the set of
test cases your team has already written and accepted. Index them alongside
Jira issues, in the same vector store, tagged source="testrail".

Retrieval for test generation then supplies real few-shot exemplars in the
team's established style and depth, instead of asking the model to invent a
format from scratch. This is what makes the system improve as it is used.

Feedback loop: record which generated cases were uploaded unedited, edited,
or discarded. Prefer accepted cases as exemplars in later retrieval.

10. Evaluation and Quality Gates (REQUIRED)
A RAG system without retrieval evaluation is unfalsifiable — a total retrieval
failure is indistinguishable from "the LLM gave a mediocre answer."

Minimum:
- A fixture set of ~20 queries with known-correct issue keys.
- Recall@k — is the correct issue present in the top-k results?
- Groundedness — does each generated test trace back to a retrieved chunk?
- Similarity floor — warn when the best match scores below ~0.45, which
  usually means nothing relevant is indexed.
- A startup self-check that embeddings, vector store, and LLM are all reachable,
  surfaced in the UI. Degraded state must be visible before a query is run,
  not inferred afterwards from bad output.

11. React UI
Create an intuitive dashboard with the following sections:
Synchronization
Connect to Jira
Full Sync
Incremental Sync
Sync Progress
Last Sync Time
Number of Issues
Number of Embeddings
Token Savings

Vector Database Explorer
Display:
Stored Documents
Metadata
Chunks
Embeddings
Similarity Search Results

RAG Explorer
For every query show:
User Query

↓

Retrieved Chunks

↓

Similarity Scores

↓

Prompt Sent to LLM

↓

Generated Response


Test Generation
Input:
Jira Issue Key

Buttons:
Generate Tests
Upload to TestRail
Display:
Generated Test Cases
Upload Status
TestRail IDs

12. Configuration
Replace the PDF configuration with Jira, Vector DB, and TestRail settings.
.env
# Jira Configuration
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_PROJECT_KEY=ABC
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token
JIRA_MCP_SERVER=http://localhost:8080

# Optional Atlassian API
JIRA_USE_MCP=true

# TestRail Configuration
TESTRAIL_BASE_URL=https://company.testrail.io
TESTRAIL_PROJECT_ID=1
TESTRAIL_SUITE_ID=1
TESTRAIL_SECTION_ID=1
TESTRAIL_USERNAME=your-email@example.com
TESTRAIL_API_KEY=your-api-key
TESTRAIL_MCP_SERVER=http://localhost:8090

# Vector Database
VECTOR_DB=chromadb
CHROMA_DB_PATH=./chromadb

# Embedding Model (local ONNX — no server, no API key)
EMBEDDING_PROVIDER=fastembed
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
FASTEMBED_CACHE_DIR=./model_cache

# LLM
# Note: Groq's GPT-OSS model ID is "openai/gpt-oss-120b" — there is no
# "opengpt-oss-120b". Verify IDs against the provider's model list.
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=your-groq-api-key

# Synchronization
ENABLE_INCREMENTAL_SYNC=true
SYNC_INTERVAL_MINUTES=30
CHUNK_SIZE=800
CHUNK_OVERLAP=150
TOP_K_RESULTS=5

# Logging
LOG_LEVEL=INFO


13. Configuration File (config.yaml)
jira:
  project_key: ABC
  issue_types:
    - Story
    - Bug

  fields:
    - summary
    - description
    - acceptanceCriteria
    - priority
    - labels
    - components
    - sprint
    - status

sync:
  mode: incremental
  change_detection:
    timestamp: true
    hash: true
    delete_detection: true

vector_db:
  provider: chromadb
  collection: jira_knowledge

retrieval:
  top_k: 5

test_generation:
  generate_manual: true
  generate_api: true
  generate_ui: true
  generate_regression: true

testrail:
  auto_upload: true


14. Required Information from the User
Before running the application, prompt for or configure the following:
Jira
Jira Base URL
Jira Cloud/Data Center type
Jira Project Key(s)
Jira API Token (or MCP server endpoint)
Jira User Email (for REST API authentication)
Jira MCP Server URL (if used)
Issue types to synchronize (Story, Bug, Task, Epic, etc.)
Custom field IDs (e.g., Acceptance Criteria, Story Points, Sprint) if applicable
JQL filter (optional)
Synchronization interval
TestRail
TestRail Base URL
TestRail API Key
Username/Email
Project ID
Suite ID
Section ID
TestRail MCP Server URL
Default template or case type (optional)
AI / Vector Store
Groq API Key
Embedding model selection
ChromaDB storage path
Chunk size and overlap
Top-K retrieval value

15. Expected Outcome
The completed platform should:
Ingest Jira User Stories and Bugs into a Vector Database.
Perform efficient incremental synchronization using timestamp and hash-based change detection.
Minimize LLM token usage by retrieving only relevant embedded content instead of repeatedly querying Jira.
Use Retrieval-Augmented Generation (RAG) to generate high-quality manual and automation-oriented test cases.
Automatically upload generated test cases to the appropriate TestRail project through the TestRail MCP Server.
Provide a visual dashboard showing synchronization status, retrieved context, token savings, vector database contents, and the complete RAG workflow for demonstrations and production readiness.
This design scales well for organizations managing 30+ applications, significantly reducing token consumption while improving response quality, synchronization efficiency, and reuse of testing knowledge across projects.

