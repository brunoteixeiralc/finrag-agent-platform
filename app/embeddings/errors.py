"""Stable errors that never expose embedding inputs or values."""

from enum import StrEnum


class EmbeddingErrorCode(StrEnum):
    """Machine-readable failures for embedding validation."""

    INVALID_INPUT_INDEX = "invalid_input_index"
    INVALID_CONTENT = "invalid_content"
    INVALID_TASK_TYPE = "invalid_task_type"
    INVALID_TITLE = "invalid_title"
    INVALID_MODEL = "invalid_model"
    INVALID_DIMENSIONS = "invalid_dimensions"
    NON_NUMERIC_VALUE = "non_numeric_value"
    NON_FINITE_VALUE = "non_finite_value"
    ZERO_NORM = "zero_norm"
    NOT_NORMALIZED = "not_normalized"


class EmbeddingValidationError(ValueError):
    """Content-safe validation failure for embedding contracts."""

    def __init__(
        self,
        code: EmbeddingErrorCode,
        message: str,
        *,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.field = field
