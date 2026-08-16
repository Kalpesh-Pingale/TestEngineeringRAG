import json
import logging
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from app.config import settings
from app.models.rag import RetrievedChunk

logger = logging.getLogger(__name__)


class VectorStore:
    """Local file-based vector store with cosine similarity search.

    Vectors are stored as a single .npy matrix and metadata as JSONL. Writes are
    explicit via flush() so a bulk sync performs one write instead of one write
    per chunk.
    """

    def __init__(self, persist_dir: str = ""):
        self.persist_dir = Path(persist_dir or settings.chroma_db_path)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.vectors_file = self.persist_dir / "vectors.npy"
        self.legacy_file = self.persist_dir / "vectors.pkl"
        self.metadata_file = self.persist_dir / "metadata.jsonl"
        self._vectors: List[List[float]] = []
        self._metadatas: List[Dict[str, Any]] = []
        self._ids: List[str] = []
        self._matrix: Optional[np.ndarray] = None  # normalized, built lazily
        self._dirty = False
        self._load()

    # --- Persistence ---

    def _load(self):
        self._vectors, self._metadatas, self._ids = [], [], []
        self._matrix = None

        if self.metadata_file.exists():
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                self._metadatas = [json.loads(line) for line in f if line.strip()]

        if self.vectors_file.exists():
            try:
                self._vectors = np.load(self.vectors_file).tolist()
            except Exception as e:
                logger.warning(f"Failed to load {self.vectors_file}: {e}")
        elif self.legacy_file.exists():
            # Vectors written by the previous pickle-based format. Pickle can
            # execute arbitrary code on load, so this path only exists to
            # migrate old data forward and is not used for new writes.
            logger.warning(
                "Loading legacy vectors.pkl. It will be migrated to vectors.npy "
                "on the next write."
            )
            try:
                import pickle

                with open(self.legacy_file, "rb") as f:
                    self._vectors = pickle.load(f)
            except Exception as e:
                logger.warning(f"Failed to load legacy vector store: {e}")

        if len(self._vectors) != len(self._metadatas):
            logger.error(
                f"Vector/metadata mismatch ({len(self._vectors)} vs "
                f"{len(self._metadatas)}). Treating store as empty; run a Full Sync."
            )
            self._vectors, self._metadatas = [], []

        self._ids = [
            m.get("vector_id", f"v{i}") for i, m in enumerate(self._metadatas)
        ]
        if self._vectors:
            logger.info(f"Loaded {len(self._vectors)} vectors from {self.persist_dir}")

    def flush(self):
        """Write pending changes to disk. Call once after a batch of writes."""
        if not self._dirty:
            return
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        arr = (
            np.array(self._vectors, dtype=np.float32)
            if self._vectors
            else np.zeros((0, 0), dtype=np.float32)
        )
        # Write to a temp file then replace, so an interrupted write cannot
        # leave vectors and metadata out of sync.
        tmp_vec = self.vectors_file.parent / (self.vectors_file.name + ".tmp")
        tmp_meta = self.metadata_file.parent / (self.metadata_file.name + ".tmp")
        # Pass a file handle: np.save() appends ".npy" when given a path whose
        # name does not already end in it, which would break the rename below.
        with open(tmp_vec, "wb") as f:
            np.save(f, arr)
        with open(tmp_meta, "w", encoding="utf-8") as f:
            for m in self._metadatas:
                f.write(json.dumps(m) + "\n")
        tmp_vec.replace(self.vectors_file)
        tmp_meta.replace(self.metadata_file)

        if self.legacy_file.exists():
            self.legacy_file.unlink()
            logger.info("Removed legacy vectors.pkl after migration")

        self._dirty = False

    def reload(self):
        """Reload from disk, picking up changes made by another instance."""
        self._load()

    def clear_all(self):
        self._vectors, self._metadatas, self._ids = [], [], []
        self._matrix = None
        self._dirty = True
        self.flush()

    @property
    def count(self) -> int:
        return len(self._vectors)

    # --- Embedding provenance ---

    def embedding_versions(self) -> set:
        """Distinct embedding versions present in the store."""
        return {
            m.get("embedding_version", "unknown")
            for m in self._metadatas
            if m.get("embedding_version")
        }

    def check_compatibility(self, active_version: str) -> dict:
        """Verify stored vectors were built with the model now in use.

        Vectors from different models are not comparable — cosine similarity
        between them is meaningless — so a mismatch must block RAG queries
        rather than silently returning nonsense.
        """
        if not self._vectors:
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
        self._vectors.append(vector)
        self._metadatas.append(metadata)
        self._ids.append(vid)
        self._matrix = None
        self._dirty = True
        if flush:
            self.flush()
        return vid

    def update_embedding(
        self, vector_id: str, vector: List[float], metadata: Dict[str, Any]
    ) -> bool:
        if vector_id not in self._ids:
            return False
        idx = self._ids.index(vector_id)
        self._vectors[idx] = vector
        metadata["vector_id"] = vector_id
        self._metadatas[idx] = metadata
        self._matrix = None
        self._dirty = True
        self.flush()
        return True

    def delete_by_issue_key(self, issue_key: str, flush: bool = True) -> int:
        indices = [
            i for i, m in enumerate(self._metadatas) if m.get("issue_key") == issue_key
        ]
        for i in sorted(indices, reverse=True):
            del self._vectors[i]
            del self._metadatas[i]
            del self._ids[i]
        if indices:
            self._matrix = None
            self._dirty = True
            if flush:
                self.flush()
        return len(indices)

    # --- Reads ---

    def get_by_issue_key(self, issue_key: str) -> List[Dict[str, Any]]:
        return [
            {"vector_id": self._ids[i], "metadata": m, "id": self._ids[i]}
            for i, m in enumerate(self._metadatas)
            if m.get("issue_key") == issue_key
        ]

    def _normalized_matrix(self) -> np.ndarray:
        """Cache the L2-normalized matrix so repeated searches skip the work."""
        if self._matrix is None:
            arr = np.array(self._vectors, dtype=np.float32)
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            self._matrix = arr / np.maximum(norms, 1e-10)
        return self._matrix

    def similarity_search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        where: Optional[Callable[[Dict[str, Any]], bool]] = None,
        exclude_ids: Optional[set] = None,
    ) -> List[RetrievedChunk]:
        """Cosine similarity search with an optional metadata filter.

        `where` narrows the candidate set before ranking, which is what makes
        issue-scoped retrieval possible (e.g. "only chunks for SCRUM-17").
        """
        if not self._vectors or top_k <= 0:
            return []

        candidates = range(len(self._vectors))
        if where is not None:
            candidates = [i for i in candidates if where(self._metadatas[i])]
        if exclude_ids:
            candidates = [i for i in candidates if self._ids[i] not in exclude_ids]
        candidates = list(candidates)
        if not candidates:
            return []

        query = np.array(query_vector, dtype=np.float32)
        query = query / max(float(np.linalg.norm(query)), 1e-10)

        matrix = self._normalized_matrix()
        if matrix.shape[1] != query.shape[0]:
            raise ValueError(
                f"Query vector has {query.shape[0]} dimensions but the store holds "
                f"{matrix.shape[1]}-dimensional vectors. The embedding model changed — "
                "run a Full Sync to rebuild."
            )

        sims = matrix[candidates] @ query
        k = min(top_k, len(candidates))
        # argpartition finds the top-k without fully sorting all N.
        top_local = np.argpartition(-sims, k - 1)[:k]
        top_local = top_local[np.argsort(-sims[top_local])]

        results = []
        for local_idx in top_local:
            idx = candidates[int(local_idx)]
            meta = self._metadatas[idx]
            results.append(
                RetrievedChunk(
                    content=meta.get("content", ""),
                    issue_key=meta.get("issue_key", ""),
                    project_key=meta.get("project_key", ""),
                    issue_type=meta.get("issue_type", ""),
                    similarity_score=float(sims[int(local_idx)]),
                    metadata=meta,
                )
            )
        return results

    def get_all_metadata(self) -> List[Dict[str, Any]]:
        return self._metadatas

    def get_issue_keys(self) -> set:
        return {m.get("issue_key") for m in self._metadatas if m.get("issue_key")}
