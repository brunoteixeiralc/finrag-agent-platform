"""Pure L2 normalization for the fixed embedding index version."""

import math
from collections.abc import Iterable

from app.embeddings.errors import EmbeddingErrorCode, EmbeddingValidationError
from app.embeddings.models import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EmbeddingTaskType,
    EmbeddingVector,
)


def normalize_embedding(values: Iterable[object]) -> tuple[float, ...]:
    """Validate and L2-normalize exactly 768 numeric values."""

    try:
        received = tuple(values)
    except TypeError as error:
        raise EmbeddingValidationError(
            EmbeddingErrorCode.NON_NUMERIC_VALUE,
            "The embedding must be an iterable of numeric values.",
            field="values",
        ) from error

    if len(received) != EMBEDDING_DIMENSIONS:
        raise EmbeddingValidationError(
            EmbeddingErrorCode.INVALID_DIMENSIONS,
            f"The embedding must contain exactly {EMBEDDING_DIMENSIONS} values.",
            field="values",
        )

    numeric_values: list[float] = []
    for value in received:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise EmbeddingValidationError(
                EmbeddingErrorCode.NON_NUMERIC_VALUE,
                "The embedding must contain only numeric values.",
                field="values",
            )
        try:
            numeric_value = float(value)
        except OverflowError as error:
            raise EmbeddingValidationError(
                EmbeddingErrorCode.NON_FINITE_VALUE,
                "The embedding must contain only finite values.",
                field="values",
            ) from error
        if not math.isfinite(numeric_value):
            raise EmbeddingValidationError(
                EmbeddingErrorCode.NON_FINITE_VALUE,
                "The embedding must contain only finite values.",
                field="values",
            )
        numeric_values.append(numeric_value)

    norm = math.hypot(*numeric_values)
    if norm == 0:
        raise EmbeddingValidationError(
            EmbeddingErrorCode.ZERO_NORM,
            "The embedding norm must be greater than zero.",
            field="values",
        )
    if not math.isfinite(norm):
        raise EmbeddingValidationError(
            EmbeddingErrorCode.NON_FINITE_VALUE,
            "The embedding norm must be finite.",
            field="values",
        )

    return tuple(value / norm for value in numeric_values)


def create_embedding_vector(
    values: Iterable[object],
    *,
    input_index: int,
    task_type: EmbeddingTaskType,
    model: str = EMBEDDING_MODEL,
) -> EmbeddingVector:
    """Build a validated immutable vector from provider values."""

    return EmbeddingVector(
        input_index=input_index,
        task_type=task_type,
        values=normalize_embedding(values),
        model=model,
    )
