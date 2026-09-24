import logging
from typing import List

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models.sync import ProjectSyncSummary, SyncResult, SyncStatus, SyncMetadata
from app.models.requests import SyncRequest
from app.services.sync_service import SyncInProgressError, SyncService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sync", tags=["sync"])

sync_service = SyncService()


@router.post("/full", response_model=SyncResult)
async def full_sync(req: SyncRequest):
    try:
        result = await sync_service.run_full_sync(
            project_key=req.project_key or "",
            issue_types=req.issue_types,
        )
        return result
    except SyncInProgressError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/incremental", response_model=SyncResult)
async def incremental_sync(req: SyncRequest):
    try:
        result = await sync_service.run_incremental_sync(
            project_key=req.project_key or "",
            issue_types=req.issue_types,
        )
        return result
    except SyncInProgressError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=SyncStatus)
async def sync_status() -> SyncStatus:
    return sync_service.get_status()


@router.get("/metadata", response_model=SyncMetadata)
async def sync_metadata(project_key: str = "") -> SyncMetadata:
    return sync_service.get_sync_metadata(project_key)


@router.get("/projects", response_model=List[ProjectSyncSummary])
async def list_projects() -> List[ProjectSyncSummary]:
    metas = sync_service.get_all_projects_metadata()
    default_pk = settings.default_project_key
    return [
        ProjectSyncSummary(
            project_key=pk,
            last_sync_time=meta.last_sync_time,
            total_issues=meta.total_issues,
            total_embeddings=meta.total_embeddings,
            embedding_version=meta.embedding_version,
            is_default=(pk == default_pk),
        )
        for pk, meta in metas.items()
    ]
