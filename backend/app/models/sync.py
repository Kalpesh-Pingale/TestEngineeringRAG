from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel


class SyncMetadata(BaseModel):
    last_sync_time: Optional[str] = None
    total_issues: int = 0
    total_embeddings: int = 0
    total_tokens_saved: int = 0
    issue_hashes: Dict[str, str] = {}  # issue_key -> content_hash
    # Which model built the current vectors. A mismatch against the active
    # model means the store must be rebuilt before it can be queried.
    embedding_version: str = ""
    embedding_dimension: int = 0


class SyncResult(BaseModel):
    new_issues: int = 0
    updated_issues: int = 0
    deleted_issues: int = 0
    skipped_issues: int = 0
    total_tokens_saved: int = 0
    total_embeddings: int = 0
    last_sync_time: str = ""


class SyncStatus(BaseModel):
    is_running: bool = False
    progress: int = 0
    current_phase: str = ""
    result: Optional[SyncResult] = None
