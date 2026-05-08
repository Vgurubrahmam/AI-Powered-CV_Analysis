"""Embeddings integration sub-package."""

from app.integrations.embeddings.client import get_embedding_client, EmbeddingClient

__all__ = ["get_embedding_client", "EmbeddingClient"]
