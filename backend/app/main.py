import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import sync, vector_store, rag, testrail, config_api
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Test Engineering RAG Platform",
    description="AI-powered Test Engineering platform using Jira MCP + TestRail MCP + Vector Database",
    version="1.0.0",
)

# CORS
#
# Origins are normalised rather than used verbatim. A browser's Origin header
# is scheme + host + port with no path, so a configured value carrying a
# trailing slash — the natural thing to paste from a browser address bar —
# matches nothing, and every request fails in the browser while curl still
# works. Silent and slow to diagnose, so strip it here.
def _parse_origins(raw: str) -> list[str]:
    origins = [o.strip().rstrip("/") for o in raw.split(",")]
    return [o for o in origins if o]


allowed_origins = _parse_origins(settings.cors_origins)
logger.info(f"CORS allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(sync.router)
app.include_router(vector_store.router)
app.include_router(rag.router)
app.include_router(testrail.router)
app.include_router(config_api.router)


@app.get("/api/health")
async def health():
    """Report readiness of every dependency the RAG pipeline needs.

    The UI uses this to warn before a query silently returns poor results —
    e.g. when the vector store was built with a different embedding model.
    """
    embedder = EmbeddingService()
    embed_health = await embedder.health_check()

    store = VectorStore()
    compat = store.check_compatibility(embedder.embedding_version)

    checks = {
        "embeddings": embed_health,
        "vector_store": {
            "ready": compat["compatible"] and not compat.get("empty"),
            "vectors": store.count,
            "issues": len(store.get_issue_keys()),
            **compat,
        },
        "llm": {
            "ready": bool(settings.groq_api_key),
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            **({} if settings.groq_api_key else {"fix": "Set GROQ_API_KEY in backend/.env"}),
        },
        "jira": {
            "ready": bool(settings.jira_base_url and settings.jira_api_token),
            "project": settings.jira_project_key,
        },
        "testrail": {
            "ready": bool(settings.testrail_enabled and settings.testrail_api_key),
            "enabled": settings.testrail_enabled,
        },
    }

    required = ["embeddings", "vector_store", "llm"]
    return {
        "status": "ok" if all(checks[k]["ready"] for k in required) else "degraded",
        "service": "test-engineering-rag",
        "checks": checks,
    }
