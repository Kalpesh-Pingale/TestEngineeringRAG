import os
import logging
from typing import Any, Dict

from fastapi import APIRouter

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/")
async def get_config() -> Dict[str, Any]:
    return {
        "jira_project_key": settings.jira_project_key,
        "jira_base_url": settings.jira_base_url,
        "jira_use_mcp": settings.jira_use_mcp,
        "testrail_base_url": settings.testrail_base_url,
        "testrail_project_id": settings.testrail_project_id,
        "testrail_suite_id": settings.testrail_suite_id,
        "testrail_section_id": settings.testrail_section_id,
        "vector_db": settings.vector_db,
        "chroma_db_path": settings.chroma_db_path,
        "embedding_model": settings.embedding_model,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "enable_incremental_sync": settings.enable_incremental_sync,
        "sync_interval_minutes": settings.sync_interval_minutes,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "top_k_results": settings.top_k_results,
    }
