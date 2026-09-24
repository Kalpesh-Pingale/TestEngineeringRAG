import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.models.rag import RetrievedChunk
from app.models.requests import SearchRequest
from app.services.embedding_service import EmbeddingError, EmbeddingService
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vector", tags=["vector-store"])

vector_store = VectorStore()
embedder = EmbeddingService()


@router.get("/stats")
async def vector_stats(project_key: str = "") -> dict:
    vector_store.reload()
    pk = project_key or None
    return {
        "total_vectors": (
            vector_store.count if not pk else len(vector_store.get_all_metadata(pk))
        ),
        "unique_issues": len(vector_store.get_issue_keys(pk)),
    }


@router.get("/documents")
async def list_documents(project_key: str = "") -> List[Dict[str, Any]]:
    vector_store.reload()
    return vector_store.get_all_metadata(project_key or None)


@router.post("/search")
async def search_similar(req: SearchRequest) -> List[RetrievedChunk]:
    vector_store.reload()
    compat = vector_store.check_compatibility(embedder.embedding_version)
    if compat.get("empty"):
        return []
    if not compat["compatible"]:
        # Scores across different embedding models are meaningless, so refuse
        # rather than return a plausible-looking but arbitrary ranking.
        raise HTTPException(
            status_code=409, detail=f"{compat['reason']} {compat['fix']}"
        )

    try:
        query_vec = await embedder.generate_embedding(req.query)
        return vector_store.similarity_search(
            query_vec, top_k=req.top_k, project_key=req.project_key
        )
    except EmbeddingError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
