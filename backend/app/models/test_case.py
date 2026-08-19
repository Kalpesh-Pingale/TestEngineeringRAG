from typing import List, Optional
from pydantic import BaseModel, Field


class TestCase(BaseModel):
    title: str
    preconditions: str = ""
    steps: List[str] = Field(default_factory=list)
    expected_results: str = ""
    priority: str = "Medium"
    test_type: str = "Manual"
    automation_candidate: str = "No"
    requirement: str = ""
    jira_issue_key: str = ""


class GeneratedTests(BaseModel):
    issue_key: str
    test_cases: List[TestCase] = Field(default_factory=list)
    total_count: int = 0
    model_used: str = ""
    embedding_model: str = ""
    # Retrieval provenance: how much context came from the issue under test
    # versus related historical issues.
    target_chunk_count: int = 0
    context_chunk_count: int = 0
    # Tentative token accounting for this generation call — baseline is the raw
    # Jira payload size for this issue (a live MCP/REST fetch), not the whole corpus.
    total_tokens_used: int = 0
    baseline_tokens: int = 0
    retrieved_tokens: int = 0
    tokens_saved: int = 0
    indexed_chunk_count: int = 0


class TestRailUploadResult(BaseModel):
    test_case_id: Optional[int] = None
    testrail_url: Optional[str] = ""
    success: bool = False
    error: Optional[str] = ""
