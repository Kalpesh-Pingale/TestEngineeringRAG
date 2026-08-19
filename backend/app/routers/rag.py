import logging
from fastapi import APIRouter, HTTPException

from app.models.rag import RAGQuery, RAGResponse
from app.models.test_case import GeneratedTests
from app.models.requests import TestGenerateRequest, SimilarRequest, SearchRequest
from app.services.embedding_service import EmbeddingError
from app.services.rag_service import RAGService, RAGError
from app.services.test_generator import TestGenerator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rag", tags=["rag"])

rag_service = RAGService()
test_generator = TestGenerator()


def _handle(e: Exception) -> HTTPException:
    """Map pipeline errors to actionable HTTP responses.

    Setup problems (missing model, stale vectors, unsynced issue) are the
    caller's to fix, so they surface as 409 with the remedy in the message
    rather than as an opaque 500.
    """
    if isinstance(e, (RAGError, EmbeddingError)):
        logger.warning(f"RAG precondition failed: {e}")
        return HTTPException(status_code=409, detail=str(e))
    logger.exception("RAG request failed")
    return HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=RAGResponse)
async def query_rag(query: RAGQuery):
    try:
        return await rag_service.query(query)
    except Exception as e:
        raise _handle(e)


@router.get("/models")
async def list_models():
    try:
        return await rag_service.list_models()
    except Exception as e:
        raise _handle(e)


@router.post("/generate-tests", response_model=GeneratedTests)
async def generate_tests(req: TestGenerateRequest):
    try:
        rag_resp = await rag_service.generate_test_cases(req.issue_key, model=req.model)
        test_cases = test_generator.parse_rag_response(rag_resp)
        if not test_cases:
            raise RAGError(
                "The model returned no parseable test cases. "
                "Check the RAG Explorer tab to inspect the raw response."
            )
        return GeneratedTests(
            issue_key=req.issue_key,
            test_cases=test_cases,
            total_count=len(test_cases),
            model_used=rag_resp.model_used,
            embedding_model=rag_service.embedder.model,
            target_chunk_count=rag_resp.target_chunk_count,
            context_chunk_count=rag_resp.context_chunk_count,
            total_tokens_used=rag_resp.total_tokens_used,
            baseline_tokens=rag_resp.baseline_tokens,
            retrieved_tokens=rag_resp.retrieved_tokens,
            tokens_saved=rag_resp.tokens_saved,
            indexed_chunk_count=rag_resp.indexed_chunk_count,
        )
    except Exception as e:
        raise _handle(e)


@router.post("/similar")
async def find_similar(req: SimilarRequest):
    try:
        return await rag_service.similar_stories(req.issue_key, req.top_k)
    except Exception as e:
        raise _handle(e)


@router.post("/semantic-search", response_model=RAGResponse)
async def semantic_search(req: SearchRequest):
    try:
        return await rag_service.semantic_search(req.query, req.top_k)
    except Exception as e:
        raise _handle(e)
