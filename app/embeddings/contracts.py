"""Ports implemented by future embedding providers."""

from typing import Protocol

from app.embeddings.models import EmbeddingRequest, EmbeddingVector


class EmbeddingGateway(Protocol):
    """Provider-independent asynchronous embedding boundary."""

    async def embed(
        self,
        requests: tuple[EmbeddingRequest, ...],
        *,
        request_id: str,
    ) -> tuple[EmbeddingVector, ...]:
        """Return one validated vector for every request in the same order."""
