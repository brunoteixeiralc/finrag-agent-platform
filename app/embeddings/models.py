"""Immutable provider-independent embedding models."""

import math
from dataclasses import dataclass, field
from enum import StrEnum

from app.embeddings.errors import EmbeddingErrorCode, EmbeddingValidationError

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768
MAX_EMBEDDING_TITLE_CHARACTERS = 200
NORMALIZED_VECTOR_TOLERANCE = 1e-6


class EmbeddingTaskType(StrEnum):
    """Task types supported by the fixed MVP embedding model."""

    DOCUMENT = "RETRIEVAL_DOCUMENT"
    QUERY = "RETRIEVAL_QUERY"


@dataclass(frozen=True, slots=True)
class EmbeddingRequest:
    """One ordered text input whose sensitive values stay out of representations."""

    input_index: int
    task_type: EmbeddingTaskType
    content: str = field(repr=False)
    title: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.input_index, bool)
            or not isinstance(self.input_index, int)
            or self.input_index < 0
        ):
            raise EmbeddingValidationError(
                EmbeddingErrorCode.INVALID_INPUT_INDEX,
                "The embedding input index must be a non-negative integer.",
                field="input_index",
            )
        if not isinstance(self.task_type, EmbeddingTaskType):
            raise EmbeddingValidationError(
                EmbeddingErrorCode.INVALID_TASK_TYPE,
                "The embedding task type is invalid.",
                field="task_type",
            )
        if not isinstance(self.content, str) or not self.content.strip():
            raise EmbeddingValidationError(
                EmbeddingErrorCode.INVALID_CONTENT,
                "Embedding content must be non-empty text.",
                field="content",
            )
        if self.title is not None and (
            not isinstance(self.title, str)
            or not self.title.strip()
            or len(self.title) > MAX_EMBEDDING_TITLE_CHARACTERS
            or self.task_type is not EmbeddingTaskType.DOCUMENT
        ):
            raise EmbeddingValidationError(
                EmbeddingErrorCode.INVALID_TITLE,
                "The embedding title is invalid for this task.",
                field="title",
            )


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    """One normalized vector tied to its ordered input and index version."""

    input_index: int
    task_type: EmbeddingTaskType
    values: tuple[float, ...] = field(repr=False)
    model: str = EMBEDDING_MODEL
    dimensions: int = EMBEDDING_DIMENSIONS

    def __post_init__(self) -> None:
        if (
            isinstance(self.input_index, bool)
            or not isinstance(self.input_index, int)
            or self.input_index < 0
        ):
            raise EmbeddingValidationError(
                EmbeddingErrorCode.INVALID_INPUT_INDEX,
                "The embedding input index must be a non-negative integer.",
                field="input_index",
            )
        if not isinstance(self.task_type, EmbeddingTaskType):
            raise EmbeddingValidationError(
                EmbeddingErrorCode.INVALID_TASK_TYPE,
                "The embedding task type is invalid.",
                field="task_type",
            )
        if self.model != EMBEDDING_MODEL:
            raise EmbeddingValidationError(
                EmbeddingErrorCode.INVALID_MODEL,
                "The embedding model does not match the active index version.",
                field="model",
            )
        if not isinstance(self.values, tuple):
            raise EmbeddingValidationError(
                EmbeddingErrorCode.NON_NUMERIC_VALUE,
                "The embedding must be an immutable tuple of floating-point values.",
                field="values",
            )
        if self.dimensions != EMBEDDING_DIMENSIONS or len(self.values) != EMBEDDING_DIMENSIONS:
            raise EmbeddingValidationError(
                EmbeddingErrorCode.INVALID_DIMENSIONS,
                f"The embedding must contain exactly {EMBEDDING_DIMENSIONS} values.",
                field="values",
            )
        if any(type(value) is not float for value in self.values):
            raise EmbeddingValidationError(
                EmbeddingErrorCode.NON_NUMERIC_VALUE,
                "The embedding must contain only floating-point values.",
                field="values",
            )
        if not all(math.isfinite(value) for value in self.values):
            raise EmbeddingValidationError(
                EmbeddingErrorCode.NON_FINITE_VALUE,
                "The embedding must contain only finite values.",
                field="values",
            )

        norm = math.hypot(*self.values)
        if norm == 0:
            raise EmbeddingValidationError(
                EmbeddingErrorCode.ZERO_NORM,
                "The embedding norm must be greater than zero.",
                field="values",
            )
        if not math.isclose(norm, 1.0, rel_tol=NORMALIZED_VECTOR_TOLERANCE, abs_tol=0.0):
            raise EmbeddingValidationError(
                EmbeddingErrorCode.NOT_NORMALIZED,
                "The embedding must be L2-normalized.",
                field="values",
            )
