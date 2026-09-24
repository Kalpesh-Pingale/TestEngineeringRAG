import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set

from app.config import settings
from app.models.sync import SyncMetadata, SyncResult, SyncStatus
from app.models.jira import JiraIssue, JiraIssueChunk
from app.services.chunker import TextChunker
from app.services.embedding_service import EmbeddingService
from app.services.jira_service import JiraService
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Legacy single-project metadata file, kept as the fallback for deployments
# with no project configured at all, and as the migration source the first
# time a per-project file is resolved (see _sync_meta_file/_load_sync_metadata).
SYNC_META_FILE = Path(settings.chroma_db_path) / "sync_metadata.json"
_SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _sync_meta_file(project_key: str) -> Path:
    """Resolve a project key to its metadata file.

    Resolves a blank project_key through settings.default_project_key exactly
    like run_full_sync/run_incremental_sync do, so a sync run with no
    explicit project_key and a metadata read with no query param always
    agree on which file they're using.
    """
    pk = (project_key or settings.default_project_key or "").strip().upper()
    if not pk or not _SAFE_KEY_RE.match(pk):
        return SYNC_META_FILE
    return Path(settings.chroma_db_path) / f"sync_metadata.{pk}.json"


class SyncInProgressError(RuntimeError):
    """Raised when a sync is requested while another is already running."""


class SyncService:
    """Handles full and incremental synchronization of Jira data to vector DB."""

    def __init__(
        self,
        jira_service: Optional[JiraService] = None,
        chunker: Optional[TextChunker] = None,
        embedder: Optional[EmbeddingService] = None,
        vector_store: Optional[VectorStore] = None,
    ):
        self.jira_service = jira_service or JiraService()
        self.chunker = chunker or TextChunker()
        self.embedder = embedder or EmbeddingService()
        self.vector_store = vector_store or VectorStore()
        self.status = SyncStatus()
        self._lock = asyncio.Lock()

    # --- Sync Metadata ---

    def _load_sync_metadata(self, project_key: str = "") -> SyncMetadata:
        meta_file = _sync_meta_file(project_key)
        if meta_file.exists():
            try:
                return SyncMetadata(**json.loads(meta_file.read_text()))
            except Exception as e:
                logger.warning(f"Failed to load sync metadata ({meta_file.name}): {e}")
                return SyncMetadata()

        # First load after upgrading to multi-project support: no per-project
        # file yet. If this is the default project and the old global file
        # exists, adopt it as this project's metadata (and persist it under
        # the new name) so an existing deployment doesn't look "never synced"
        # and pay for a needless full re-embed.
        resolved_pk = (project_key or settings.default_project_key or "").strip().upper()
        is_default = resolved_pk == settings.default_project_key
        if is_default and meta_file != SYNC_META_FILE and SYNC_META_FILE.exists():
            try:
                legacy = SyncMetadata(**json.loads(SYNC_META_FILE.read_text()))
                self._save_sync_metadata(legacy, project_key)
                logger.info(f"Migrated legacy sync_metadata.json -> {meta_file.name}")
                return legacy
            except Exception as e:
                logger.warning(f"Failed to migrate legacy sync metadata: {e}")
        return SyncMetadata()

    def _save_sync_metadata(self, meta: SyncMetadata, project_key: str = ""):
        meta_file = _sync_meta_file(project_key)
        meta_file.parent.mkdir(parents=True, exist_ok=True)
        meta_file.write_text(meta.model_dump_json(indent=2))

    # --- Token Estimation ---

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    # --- Embedding ---

    async def _embed_and_store(self, chunks, issue) -> int:
        """Embed an issue's chunks in one batch and stage them for writing.

        Every vector is stamped with the model that produced it, so a later
        model change is detectable instead of silently corrupting search.
        """
        if not chunks:
            return 0

        vectors = await self.embedder.generate_embeddings(
            [c.content for c in chunks]
        )
        for chunk, vec in zip(chunks, vectors):
            self.vector_store.add_embedding(
                vector=vec,
                metadata={
                    "issue_key": chunk.issue_key,
                    "project_key": chunk.project_key,
                    "issue_type": chunk.issue_type,
                    "updated_timestamp": issue.updated_date,
                    "embedding_version": self.embedder.embedding_version,
                    "embedding_model": self.embedder.model,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "summary": issue.summary,
                    "raw_fetch_tokens": issue.raw_fetch_tokens,
                },
                flush=False,
            )
        return len(chunks)

    # --- Full Sync ---

    async def run_full_sync(
        self,
        project_key: str = "",
        issue_types=None,
    ) -> SyncResult:
        if self._lock.locked():
            raise SyncInProgressError(
                f"A sync is already running for project "
                f"'{self.status.project_key or '?'}'. Wait for it to finish."
            )
        async with self._lock:
            return await self._do_full_sync(project_key, issue_types)

    async def _do_full_sync(
        self,
        project_key: str = "",
        issue_types=None,
    ) -> SyncResult:
        resolved_pk = (project_key or settings.default_project_key or "").strip().upper()
        self.status = SyncStatus(
            is_running=True,
            progress=0,
            current_phase="Fetching issues from Jira...",
            project_key=resolved_pk,
        )

        issues = await self.jira_service.fetch_all_issues(
            project_key=resolved_pk, issue_types=issue_types
        )
        self.status.current_phase = "Processing issues..."
        meta = self._load_sync_metadata(resolved_pk)
        result = SyncResult(project_key=resolved_pk)

        # Clear only this project's vectors — clear_all() would wipe every
        # other project's data too. Fall back to clear_all() only when no
        # project is configured at all (pre-existing single-store setup).
        if resolved_pk:
            self.vector_store.clear_project(resolved_pk)
        else:
            self.vector_store.clear_all()
        meta.total_embeddings = 0
        meta.total_issues = 0
        meta.total_tokens_saved = 0
        meta.issue_hashes = {}

        for i, issue in enumerate(issues):
            content_hash = self.jira_service.compute_content_hash(issue)
            meta.issue_hashes[issue.issue_key] = content_hash

            chunks = self.chunker.chunk_issue(issue)
            meta.total_embeddings += await self._embed_and_store(chunks, issue)

            meta.total_issues += 1
            result.new_issues += 1

            if (i + 1) % 10 == 0:
                self.status.progress = int((i + 1) / len(issues) * 100)

        # One disk write for the whole sync instead of one per chunk.
        self.vector_store.flush()

        meta.embedding_version = self.embedder.embedding_version
        meta.embedding_dimension = self.embedder.dimension
        now = datetime.now(timezone.utc).isoformat()
        meta.last_sync_time = now
        result.last_sync_time = now
        result.total_embeddings = meta.total_embeddings
        result.total_tokens_saved = meta.total_tokens_saved
        self._save_sync_metadata(meta, resolved_pk)

        self.status = SyncStatus(
            is_running=False, progress=100, result=result, project_key=resolved_pk
        )
        logger.info(
            f"Full sync complete for {resolved_pk or '(unconfigured)'}. "
            f"{result.new_issues} new issues."
        )
        return result

    # --- Incremental Sync ---

    async def run_incremental_sync(
        self,
        project_key: str = "",
        issue_types=None,
    ) -> SyncResult:
        if self._lock.locked():
            raise SyncInProgressError(
                f"A sync is already running for project "
                f"'{self.status.project_key or '?'}'. Wait for it to finish."
            )
        async with self._lock:
            resolved_pk = (project_key or settings.default_project_key or "").strip().upper()
            self.status = SyncStatus(
                is_running=True,
                progress=0,
                current_phase="Checking for changes...",
                project_key=resolved_pk,
            )

            meta = self._load_sync_metadata(resolved_pk)
            result = SyncResult(project_key=resolved_pk)
            now = datetime.now(timezone.utc).isoformat()

            if not meta.last_sync_time:
                logger.info("No prior sync found. Running full sync instead.")
                return await self._do_full_sync(
                    project_key=resolved_pk, issue_types=issue_types
                )

            # Fetch issues updated since last sync
            changed_issues = await self.jira_service.fetch_incremental_issues(
                last_sync_time=meta.last_sync_time,
                project_key=resolved_pk,
                issue_types=issue_types,
            )

            self.status.current_phase = "Processing changed issues..."
            issues_processed = 0
            total_to_process = len(changed_issues)

            for issue in changed_issues:
                new_hash = self.jira_service.compute_content_hash(issue)
                existing_hash = meta.issue_hashes.get(issue.issue_key)

                if existing_hash == new_hash:
                    # Skip — unchanged
                    result.skipped_issues += 1
                    tokens_saved = self._estimate_tokens(
                        f"{issue.summary} {issue.description or ''}"
                    )
                    meta.total_tokens_saved += tokens_saved
                    result.total_tokens_saved = meta.total_tokens_saved
                else:
                    # Changed or new
                    self.vector_store.delete_by_issue_key(issue.issue_key, flush=False)
                    chunks = self.chunker.chunk_issue(issue)
                    meta.total_embeddings += await self._embed_and_store(chunks, issue)

                    meta.issue_hashes[issue.issue_key] = new_hash
                    if existing_hash:
                        result.updated_issues += 1
                    else:
                        result.new_issues += 1

                issues_processed += 1
                if total_to_process > 0:
                    self.status.progress = int(
                        issues_processed / total_to_process * 100
                    )

            self.vector_store.flush()

            meta.embedding_version = self.embedder.embedding_version
            meta.embedding_dimension = self.embedder.dimension
            meta.last_sync_time = now
            result.last_sync_time = now
            result.total_embeddings = meta.total_embeddings
            self._save_sync_metadata(meta, resolved_pk)

            self.status = SyncStatus(
                is_running=False, progress=100, result=result, project_key=resolved_pk
            )
            logger.info(
                f"Incremental sync complete for {resolved_pk or '(unconfigured)'}. "
                f"+{result.new_issues} new, +{result.updated_issues} updated, "
                f"-{result.deleted_issues} deleted, {result.skipped_issues} skipped"
            )
            return result

    def get_status(self) -> SyncStatus:
        return self.status

    def get_sync_metadata(self, project_key: str = "") -> SyncMetadata:
        return self._load_sync_metadata(project_key)

    def get_all_projects_metadata(self) -> Dict[str, SyncMetadata]:
        """One entry per configured project, for the /api/sync/projects listing."""
        return {pk: self._load_sync_metadata(pk) for pk in settings.project_keys}
