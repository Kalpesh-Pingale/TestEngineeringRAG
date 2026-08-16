from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class JiraIssue(BaseModel):
    issue_key: str
    project_key: str
    issue_type: str
    summary: str
    description: Optional[str] = ""
    acceptance_criteria: Optional[str] = ""
    priority: Optional[str] = ""
    status: Optional[str] = ""
    sprint: Optional[str] = ""
    labels: List[str] = Field(default_factory=list)
    components: List[str] = Field(default_factory=list)
    story_points: Optional[float] = None
    created_date: Optional[str] = ""
    updated_date: Optional[str] = ""
    reporter: Optional[str] = ""
    assignee: Optional[str] = ""
    linked_issues: List[str] = Field(default_factory=list)
    comments: List[str] = Field(default_factory=list)


class JiraIssueChunk(BaseModel):
    chunk_id: str
    issue_key: str
    project_key: str
    issue_type: str
    content: str
    chunk_index: int
    metadata: dict = Field(default_factory=dict)


class ChunkEmbedding(BaseModel):
    id: str
    vector: List[float]
    metadata: dict = Field(default_factory=dict)
