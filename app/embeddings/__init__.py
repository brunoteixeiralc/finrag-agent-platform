"""Provider-independent embedding contracts and vector validation."""

from app.embeddings.contracts import EmbeddingGateway
from app.embeddings.errors import EmbeddingErrorCode, EmbeddingValidationError
from app.embeddings.models import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EmbeddingRequest,
    EmbeddingTaskType,
    EmbeddingVector,
)
from app.embeddings.normalization import create_embedding_vector, normalize_embedding

__all__ = [
    "EMBEDDING_DIMENSIONS",
    "EMBEDDING_MODEL",
    "EmbeddingErrorCode",
    "EmbeddingGateway",
    "EmbeddingRequest",
    "EmbeddingTaskType",
    "EmbeddingValidationError",
    "EmbeddingVector",
    "create_embedding_vector",
    "normalize_embedding",
]
