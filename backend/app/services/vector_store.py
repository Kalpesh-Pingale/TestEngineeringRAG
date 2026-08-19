import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.models.rag import RetrievedChunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "jira_issues"

# Shared across every VectorStore instance so repeated instantiations against the
# same persist_dir (main.py, rag_service.py, sync_service.py, routers/vector_store.py
# each construct their own) resolve to Chroma's cached client for that path instead
# of opening competing connections.
_CHROMA_SETTINGS = ChromaSettings(anonymized_telemetry=False)


class VectorStore:
    """ChromaDB-backed vector store (embedded/persistent mode, no server process).

    Writes are batched: add_embedding() stages in memory and flush() performs one
    collection.add() call, so a bulk sync still does one write instead of one per
    chunk.
    """

    def __init__(self, persist_dir: str = ""):
        self.persist_dir = Path(persist_dir or settings.chroma_db_path)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self.persist_dir), settings=_CHROMA_SETTINGS
        )
        self._pending_ids: List[str] = []
        self._pending_vectors: List[List[float]] = []
        self._pending_metadatas: List[Dict[str, Any]] = []

    @property
    def _collection(self):
        """Re-resolved on every access rather than cached.

        Another VectorStore instance in this process (e.g. sync_service mid Full
        Sync) can delete and recreate the collection via clear_all(), which gets
        a new Chroma-internal collection id. A cached handle would then point at
        a deleted collection and every call would 404.
        """
        return self._client.get_or_create_collection(
            name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )

    # --- Persistence ---

    def flush(self):
        """Write staged additions. Call once after a batch of add_embedding()s."""
        if not self._pending_ids:
            return
        self._collection.add(
            ids=self._pending_ids,
            embeddings=self._pending_vectors,
            metadatas=self._pending_metadatas,
        )
        self._pending_ids, self._pending_vectors, self._pending_metadatas = [], [], []

    def reload(self):
        """No-op: _collection re-resolves on every access, nothing to refresh."""

    def clear_all(self):
        self._pending_ids, self._pending_vectors, self._pending_metadatas = [], [], []
        self._client.delete_collection(name=COLLECTION_NAME)

    @property
    def count(self) -> int:
        return self._collection.count()

    # --- Embedding provenance ---

    def embedding_versions(self) -> set:
        """Distinct embedding versions present in the store."""
        return {
            m.get("embedding_version", "unknown")
            for m in self.get_all_metadata()
            if m.get("embedding_version")
        }

    def check_compatibility(self, active_version: str) -> dict:
        """Verify stored vectors were built with the model now in use.

        Vectors from different models are not comparable — cosine similarity
        between them is meaningless — so a mismatch must block RAG queries
        rather than silently returning nonsense.
        """
        if self.count == 0:
            return {"compatible": True, "empty": True, "stored_versions": []}

        versions = self.embedding_versions()
        stale = versions - {active_version}
        if stale:
            return {
                "compatible": False,
                "empty": False,
                "stored_versions": sorted(versions),
                "active_version": active_version,
                "reason": (
                    f"Vector store contains embeddings from {sorted(stale)} but the "
                    f"active model is '{active_version}'. Similarity scores across "
                    "different models are meaningless."
                ),
                "fix": "Run a Full Sync to rebuild the vector store.",
            }
        return {
            "compatible": True,
            "empty": False,
            "stored_versions": sorted(versions),
            "active_version": active_version,
        }

    # --- Writes ---

    def add_embedding(
        self,
        vector: List[float],
        metadata: Dict[str, Any],
        doc_id: str = "",
        flush: bool = True,
    ) -> str:
        vid = doc_id or str(uuid.uuid4())
        metadata["vector_id"] = vid
        self._pending_ids.append(vid)
        self._pending_vectors.append(vector)
        self._pending_metadatas.append(metadata)
        if flush:
            self.flush()
        return vid

    def update_embedding(
        self, vector_id: str, vector: List[float], metadata: Dict[str, Any]
    ) -> bool:
        metadata["vector_id"] = vector_id
        self._collection.upsert(
            ids=[vector_id], embeddings=[vector], metadatas=[metadata]
        )
        return True

    def delete_by_issue_key(self, issue_key: str, flush: bool = True) -> int:
        existing = self._collection.get(
            where={"issue_key": issue_key}, include=[]
        )
        ids = existing.get("ids", [])
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    # --- Reads ---

    def get_by_issue_key(self, issue_key: str) -> List[Dict[str, Any]]:
        result = self._collection.get(
            where={"issue_key": issue_key}, include=["metadatas"]
        )
        return [
            {"vector_id": rid, "metadata": meta, "id": rid}
            for rid, meta in zip(result.get("ids", []), result.get("metadatas", []))
        ]

    def similarity_search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        exclude_issue_key: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        """Cosine similarity search, optionally excluding one issue's own chunks.

        `exclude_issue_key` is what makes issue-scoped context retrieval possible
        (e.g. "similar chunks from issues other than SCRUM-17").
        """
        if self.count == 0 or top_k <= 0:
            return []

        where = {"issue_key": {"$ne": exclude_issue_key}} if exclude_issue_key else None
        n_results = min(top_k, self.count)

        try:
            result = self._collection.query(
                query_embeddings=[query_vector],
                n_results=n_results,
                where=where,
                include=["metadatas", "distances"],
            )
        except chromadb.errors.InvalidDimensionException as e:
            raise ValueError(
                f"Query vector dimension mismatch: {e}. The embedding model "
                "changed — run a Full Sync to rebuild."
            ) from e

        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        results = []
        for meta, distance in zip(metadatas, distances):
            results.append(
                RetrievedChunk(
                    content=meta.get("content", ""),
                    issue_key=meta.get("issue_key", ""),
                    project_key=meta.get("project_key", ""),
                    issue_type=meta.get("issue_type", ""),
                    similarity_score=1.0 - float(distance),
                    metadata=meta,
                )
            )
        return results

    def get_all_metadata(self) -> List[Dict[str, Any]]:
        result = self._collection.get(include=["metadatas"])
        return result.get("metadatas", [])

    def get_issue_keys(self) -> set:
        return {m.get("issue_key") for m in self.get_all_metadata() if m.get("issue_key")}
