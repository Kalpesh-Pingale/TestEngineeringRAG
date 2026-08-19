from typing import List, Optional
from pydantic import BaseModel


class SyncRequest(BaseModel):
    project_key: Optional[str] = None
    issue_types: Optional[List[str]] = None


class TestGenerateRequest(BaseModel):
    issue_key: str
    # Optional per-call override of settings.llm_model, so a deprecated/invalid
    # default model doesn't block generation — pick another from the UI and retry.
    model: Optional[str] = None


class SimilarRequest(BaseModel):
    issue_key: str
    top_k: int = 5


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
