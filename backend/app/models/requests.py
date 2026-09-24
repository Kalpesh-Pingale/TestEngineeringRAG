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
    # Opt-in: by default "similar issues" stay within the target issue's own
    # project. Set true to search across every indexed project.
    cross_project: Optional[bool] = False


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    project_key: Optional[str] = None
