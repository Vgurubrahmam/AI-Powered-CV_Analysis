"""Embedding client — SBERT local or OpenAI API, configurable via env.

Providers:
  - "local"  → sentence-transformers (SBERT) running in-process
  - "openai" → OpenAI text-embedding-3-small via API

The active provider is chosen by EMBEDDING_PROVIDER env var.
Both implement the same async interface: embed_batch(texts) → list[list[float]].

Singleton pattern: get_embedding_client() returns the same instance per process.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Optional

import numpy as np
import structlog

from app.config import settings

log = structlog.get_logger(__name__)


class EmbeddingClient:
    """Base class / interface for embedding clients."""

    model_name: str = "unknown"

    async def warmup(self) -> None:
        """Pre-load model or verify API connectivity. Called on app startup."""
        pass

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of float vectors."""
        raise NotImplementedError


# ─── SBERT Local Client ───────────────────────────────────────────────────────

class SBERTEmbeddingClient(EmbeddingClient):
    """Local SBERT embedding via sentence-transformers.

    Loads the model lazily on first call. Uses thread executor to avoid
    blocking the event loop during encode().
    """

    def __init__(self, model_name: str = "all-mpnet-base-v2") -> None:
        self.model_name = model_name
        self._model = None
        self._lock = asyncio.Lock()

    async def _get_model(self):
        if self._model is not None:
            return self._model
        async with self._lock:
            if self._model is None:
                log.info("loading_sbert_model", model=self.model_name)
                from sentence_transformers import SentenceTransformer
                loop = asyncio.get_event_loop()
                cache_folder = settings.SENTENCE_TRANSFORMERS_HOME or None
                self._model = await loop.run_in_executor(
                    None,
                    lambda: SentenceTransformer(
                        self.model_name,
                        cache_folder=cache_folder,
                    ),
                )
                log.info("sbert_model_loaded", model=self.model_name)
        return self._model

    async def warmup(self) -> None:
        """Load SBERT model weights eagerly on startup."""
        await self._get_model()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # Truncate very long texts to avoid memory issues
        truncated = [t[:8192] if len(t) > 8192 else t for t in texts]

        model = await self._get_model()
        loop = asyncio.get_event_loop()

        def _encode():
            vectors = model.encode(
                truncated,
                convert_to_numpy=True,
                normalize_embeddings=True,  # unit norm for cosine similarity
                show_progress_bar=False,
                batch_size=32,
            )
            return vectors.tolist()

        result = await loop.run_in_executor(None, _encode)
        log.debug("sbert_embed_batch", count=len(texts), model=self.model_name)
        return result


# ─── OpenAI Embedding Client ──────────────────────────────────────────────────

class OpenAIEmbeddingClient(EmbeddingClient):
    """OpenAI text-embedding-3-small (or configurable model) via API."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
    ) -> None:
        self.model_name = model
        self._api_key = api_key
        self._base_url = "https://api.openai.com/v1/embeddings"

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        import httpx
        truncated = [t[:8000] for t in texts]

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self._base_url,
                json={"input": truncated, "model": self.model_name},
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"OpenAI Embedding API {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        # API returns items sorted by index
        sorted_items = sorted(data["data"], key=lambda x: x["index"])
        result = [item["embedding"] for item in sorted_items]

        log.debug(
            "openai_embed_batch",
            count=len(texts),
            model=self.model_name,
            usage=data.get("usage", {}),
        )
        return result


# ─── Factory ──────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_embedding_client() -> EmbeddingClient:
    """Return the configured embedding client singleton.

    Provider is selected by EMBEDDING_PROVIDER env var:
      - "local"  → SBERTEmbeddingClient
      - "openai" → OpenAIEmbeddingClient (requires OPENAI_API_KEY)
    """
    provider = settings.EMBEDDING_PROVIDER.lower()

    if provider == "openai":
        api_key = settings.OPENAI_API_KEY.get_secret_value()
        if not api_key:
            log.warning(
                "openai_api_key_missing_falling_back_to_local",
            )
        else:
            log.info("embedding_client_initialized", provider="openai")
            return OpenAIEmbeddingClient(api_key=api_key)

    # Default: local SBERT
    log.info(
        "embedding_client_initialized",
        provider="local",
        model=settings.SBERT_MODEL_NAME,
    )
    return SBERTEmbeddingClient(model_name=settings.SBERT_MODEL_NAME)
