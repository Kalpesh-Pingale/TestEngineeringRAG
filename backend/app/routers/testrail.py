import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.test_case import TestCase, TestRailUploadResult, GeneratedTests
from app.services.testrail_service import TestRailService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/testrail", tags=["testrail"])

testrail_service = TestRailService()


class UploadRequest(BaseModel):
    test_cases: List[TestCase]
    section_id: Optional[int] = None


class UploadGeneratedRequest(BaseModel):
    generated: GeneratedTests
    section_id: Optional[int] = None


@router.post("/upload", response_model=List[TestRailUploadResult])
async def upload_test_cases(req: UploadRequest):
    try:
        results = await testrail_service.upload_test_cases(
            req.test_cases, section_id=req.section_id
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-generated", response_model=List[TestRailUploadResult])
async def upload_generated_tests(req: UploadGeneratedRequest):
    try:
        results = await testrail_service.upload_test_cases(
            req.generated.test_cases, section_id=req.section_id
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
