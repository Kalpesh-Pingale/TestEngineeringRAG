import logging
from fastapi import APIRouter, HTTPException

from app.models.sync import SyncResult, SyncStatus, SyncMetadata
from app.models.requests import SyncRequest
from app.services.sync_service import SyncService

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=SyncStatus)
async def sync_status() -> SyncStatus:
    return sync_service.get_status()


@router.get("/metadata", response_model=SyncMetadata)
async def sync_metadata() -> SyncMetadata:
    return sync_service.get_sync_metadata()
