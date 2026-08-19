from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RAGQuery(BaseModel):
    query: str
    top_k: int = 5
    issue_key: Optional[str] = ""


class RetrievedChunk(BaseModel):
    content: str
    issue_key: str
    project_key: str
    issue_type: str
    similarity_score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGResponse(BaseModel):
    query: str
    retrieved_chunks: List[RetrievedChunk] = Field(default_factory=list)
    prompt_sent: str = ""
    generated_response: str = ""
    total_tokens_used: int = 0
    model_used: str = ""
    # How many retrieved chunks belong to the issue under test vs. supplied as
    # historical context from other issues.
    target_chunk_count: int = 0
    context_chunk_count: int = 0
    # Tentative token accounting. baseline = the raw Jira payload size for the
    # target issue (what a live MCP/REST fetch pasted straight into the prompt
    # would cost); retrieved = the context RAG actually sent. Zero until the
    # issue has been (re)synced with raw_fetch_tokens captured.
    baseline_tokens: int = 0
    retrieved_tokens: int = 0
    tokens_saved: int = 0
    indexed_chunk_count: int = 0
