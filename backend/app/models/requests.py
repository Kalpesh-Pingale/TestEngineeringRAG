from typing import List, Optional
from pydantic import BaseModel


class SyncRequest(BaseModel):
    project_key: Optional[str] = None
    issue_types: Optional[List[str]] = None


class TestGenerateRequest(BaseModel):
    issue_key: str


class SimilarRequest(BaseModel):
    issue_key: str
    top_k: int = 5


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
