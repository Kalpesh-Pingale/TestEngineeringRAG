import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import List, Optional

from app.config import settings
from app.models.jira import JiraIssueChunk

logger = logging.getLogger(__name__)

EMBEDDING_CACHE: dict[str, List[float]] = {}

# Stamped onto every stored vector. If the active model no longer matches what
# a vector was built with, that vector is not comparable and must be rebuilt.
DEGRADED_EMBEDDING_VERSION = "degraded-hash-v1"


class EmbeddingError(RuntimeError):
    """Raised when a real embedding cannot be produced.

    Deliberately fatal. A placeholder vector has no semantic meaning, so
    persisting one silently poisons the vector store: retrieval degrades to
    random selection with no way to distinguish good vectors from bad ones
    after the fact.
    """


class EmbeddingService:
    """Generates embeddings locally via fastembed (ONNX, no server, no API key).

    fastembed is synchronous and CPU-bound, so calls are dispatched to a worker
    thread to avoid blocking the event loop.
    """

    def __init__(self, model: str = "", provider: str = ""):
        self.provider = (provider or settings.embedding_provider).lower()
        self.model = model or settings.embedding_model
        self._model = None
        self._dimension: Optional[int] = None
        self._load_lock = asyncio.Lock()

    # --- Identity (stamped onto vectors so mismatches are detectable) ---

    @property
    def embedding_version(self) -> str:
        return f"{self.provider}:{self.model}"

    @property
    def dimension(self) -> int:
        return self._dimension or 384

    # --- Model loading ---

    async def _ensure_model(self):
        if self._model is not None:
            return
        async with self._load_lock:
            if self._model is not None:
                return
            self._model = await asyncio.to_thread(self._load_model_sync)

    def _load_model_sync(self):
        if self.provider != "fastembed":
            raise EmbeddingError(
                f"Unsupported embedding_provider '{self.provider}'. "
                "Set EMBEDDING_PROVIDER=fastembed."
            )
        # Windows without Developer Mode cannot create symlinks, which makes
        # huggingface_hub fail its first download attempt and retry noisily.
        # Copying instead is slightly larger on disk but avoids the retry loop.
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

        try:
            from fastembed import TextEmbedding
        except ImportError as e:
            raise EmbeddingError(
                "fastembed is not installed. Run: pip install fastembed"
            ) from e

        cache_dir = Path(settings.fastembed_cache_dir).resolve()
        cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Loading embedding model '{self.model}' (cache: {cache_dir})")
        try:
            model = TextEmbedding(model_name=self.model, cache_dir=str(cache_dir))
        except Exception as e:
            raise EmbeddingError(
                f"Failed to load embedding model '{self.model}': {e}. "
                "Check the model name against `TextEmbedding.list_supported_models()` "
                "and confirm network access for the first-time download."
            ) from e
        logger.info(f"Embedding model '{self.model}' ready")
        return model

    # --- Health ---

    async def health_check(self) -> dict:
        """Report readiness without raising, so callers can surface setup errors."""
        try:
            await self._ensure_model()
            probe = await self.generate_embedding("health check")
            return {
                "ready": True,
                "provider": self.provider,
                "model": self.model,
                "dimension": len(probe),
                "embedding_version": self.embedding_version,
            }
        except EmbeddingError as e:
            result = {
                "ready": False,
                "provider": self.provider,
                "model": self.model,
                "error": str(e),
            }
            # Only suggest installing when that is actually the problem;
            # a wrong model name or download failure needs a different fix.
            if "not installed" in str(e):
                result["fix"] = "pip install fastembed"
            return result
        except Exception as e:
            return {"ready": False, "provider": self.provider, "model": self.model, "error": str(e)}

    # --- Embedding ---

    async def generate_embedding(self, text: str) -> List[float]:
        vectors = await self.generate_embeddings([text])
        return vectors[0]

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts in one batch, reusing cached vectors."""
        if not texts:
            return []

        results: List[Optional[List[float]]] = [None] * len(texts)
        pending: List[int] = []
        for i, text in enumerate(texts):
            cached = EMBEDDING_CACHE.get(self._cache_key(text))
            if cached is not None:
                results[i] = cached
            else:
                pending.append(i)

        if pending:
            await self._ensure_model()
            to_embed = [texts[i] for i in pending]
            vectors = await asyncio.to_thread(self._embed_sync, to_embed)
            for idx, vec in zip(pending, vectors):
                EMBEDDING_CACHE[self._cache_key(texts[idx])] = vec
                results[idx] = vec

        out = [v for v in results if v is not None]
        if len(out) != len(texts):
            raise EmbeddingError(
                f"Produced {len(out)} embeddings for {len(texts)} inputs"
            )
        return out

    def _embed_sync(self, texts: List[str]) -> List[List[float]]:
        try:
            vectors = [v.tolist() for v in self._model.embed(texts)]
        except Exception as e:
            raise EmbeddingError(f"Embedding failed: {e}") from e

        if len(vectors) != len(texts):
            raise EmbeddingError(
                f"Model returned {len(vectors)} vectors for {len(texts)} inputs"
            )
        for vec in vectors:
            if not vec or not any(vec):
                raise EmbeddingError(
                    f"Model '{self.model}' returned an empty/zero vector"
                )

        self._dimension = len(vectors[0])
        return vectors

    async def generate_embeddings_batch(
        self, chunks: List[JiraIssueChunk]
    ) -> List[tuple[JiraIssueChunk, List[float]]]:
        vectors = await self.generate_embeddings([c.content for c in chunks])
        return list(zip(chunks, vectors))

    # --- Helpers ---

    def _cache_key(self, text: str) -> str:
        # Model is part of the key: the same text under a different model is a
        # different vector, and mixing them in one store breaks similarity search.
        return hashlib.md5(f"{self.embedding_version}::{text}".encode()).hexdigest()

    def compute_embedding_hash(self, vector: List[float]) -> str:
        vector_bytes = json.dumps(vector, sort_keys=True).encode()
        return hashlib.sha256(vector_bytes).hexdigest()[:16]
