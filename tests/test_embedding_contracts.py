"""Unit tests for provider-independent embedding contracts."""

import asyncio
import math
from dataclasses import FrozenInstanceError

import pytest

from app.embeddings import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EmbeddingErrorCode,
    EmbeddingGateway,
    EmbeddingRequest,
    EmbeddingTaskType,
    EmbeddingValidationError,
    EmbeddingVector,
    create_embedding_vector,
    normalize_embedding,
)


def raw_vector(*leading_values: object) -> list[object]:
    """Build one fixed-size provider vector for deterministic tests."""

    return [*leading_values, *([0.0] * (EMBEDDING_DIMENSIONS - len(leading_values)))]


def test_task_types_match_the_fixed_retrieval_contract() -> None:
    assert EmbeddingTaskType.DOCUMENT == "RETRIEVAL_DOCUMENT"
    assert EmbeddingTaskType.QUERY == "RETRIEVAL_QUERY"


def test_request_is_immutable_and_hides_content_and_title() -> None:
    request = EmbeddingRequest(
        input_index=3,
        task_type=EmbeddingTaskType.DOCUMENT,
        content="sensitive chunk marker",
        title="private title marker",
    )

    assert request.input_index == 3
    assert "sensitive chunk marker" not in repr(request)
    assert "private title marker" not in repr(request)
    with pytest.raises(FrozenInstanceError):
        request.input_index = 4  # type: ignore[misc]


@pytest.mark.parametrize("input_index", [-1, True, 1.5, "1"])
def test_request_rejects_invalid_input_index_without_echoing_it(input_index: object) -> None:
    with pytest.raises(EmbeddingValidationError) as captured_error:
        EmbeddingRequest(
            input_index=input_index,  # type: ignore[arg-type]
            task_type=EmbeddingTaskType.DOCUMENT,
            content="sensitive chunk marker",
        )

    assert captured_error.value.code is EmbeddingErrorCode.INVALID_INPUT_INDEX
    assert captured_error.value.field == "input_index"
    assert "sensitive chunk marker" not in str(captured_error.value)


@pytest.mark.parametrize("content", ["", "   ", b"text", None])
def test_request_rejects_invalid_content_without_echoing_it(content: object) -> None:
    with pytest.raises(EmbeddingValidationError) as captured_error:
        EmbeddingRequest(
            input_index=0,
            task_type=EmbeddingTaskType.DOCUMENT,
            content=content,  # type: ignore[arg-type]
        )

    assert captured_error.value.code is EmbeddingErrorCode.INVALID_CONTENT
    assert captured_error.value.field == "content"
    assert repr(content) not in str(captured_error.value)


def test_query_rejects_document_title_without_echoing_it() -> None:
    with pytest.raises(EmbeddingValidationError) as captured_error:
        EmbeddingRequest(
            input_index=0,
            task_type=EmbeddingTaskType.QUERY,
            content="What changed?",
            title="sensitive title marker",
        )

    assert captured_error.value.code is EmbeddingErrorCode.INVALID_TITLE
    assert "sensitive title marker" not in str(captured_error.value)


def test_normalization_returns_exactly_768_floats_with_unit_norm() -> None:
    normalized = normalize_embedding(raw_vector(3, 4))

    assert len(normalized) == EMBEDDING_DIMENSIONS
    assert all(type(value) is float for value in normalized)
    assert normalized[:2] == pytest.approx((0.6, 0.8))
    assert math.hypot(*normalized) == pytest.approx(1.0)


@pytest.mark.parametrize("size", [EMBEDDING_DIMENSIONS - 1, EMBEDDING_DIMENSIONS + 1])
def test_normalization_rejects_an_incorrect_dimension(size: int) -> None:
    with pytest.raises(EmbeddingValidationError) as captured_error:
        normalize_embedding([1.0] * size)

    assert captured_error.value.code is EmbeddingErrorCode.INVALID_DIMENSIONS
    assert captured_error.value.field == "values"


@pytest.mark.parametrize("invalid_value", [True, "0.25", None, object()])
def test_normalization_rejects_non_numeric_values_without_echoing_them(
    invalid_value: object,
) -> None:
    marker = "sensitive-vector-marker"
    values = raw_vector(1.0)
    values[10] = invalid_value

    with pytest.raises(EmbeddingValidationError) as captured_error:
        normalize_embedding(values)

    assert captured_error.value.code is EmbeddingErrorCode.NON_NUMERIC_VALUE
    assert marker not in str(captured_error.value)
    assert repr(invalid_value) not in str(captured_error.value)


@pytest.mark.parametrize("invalid_value", [math.nan, math.inf, -math.inf])
def test_normalization_rejects_non_finite_values(invalid_value: float) -> None:
    values = raw_vector(1.0)
    values[20] = invalid_value

    with pytest.raises(EmbeddingValidationError) as captured_error:
        normalize_embedding(values)

    assert captured_error.value.code is EmbeddingErrorCode.NON_FINITE_VALUE


def test_normalization_rejects_a_numeric_value_that_overflows_float() -> None:
    values = raw_vector(1.0)
    values[20] = 10**1_000

    with pytest.raises(EmbeddingValidationError) as captured_error:
        normalize_embedding(values)

    assert captured_error.value.code is EmbeddingErrorCode.NON_FINITE_VALUE


def test_normalization_rejects_a_non_iterable_input() -> None:
    with pytest.raises(EmbeddingValidationError) as captured_error:
        normalize_embedding(1)  # type: ignore[arg-type]

    assert captured_error.value.code is EmbeddingErrorCode.NON_NUMERIC_VALUE


def test_normalization_rejects_a_zero_vector() -> None:
    with pytest.raises(EmbeddingValidationError) as captured_error:
        normalize_embedding(raw_vector())

    assert captured_error.value.code is EmbeddingErrorCode.ZERO_NORM


def test_vector_factory_preserves_identity_and_hides_values() -> None:
    vector = create_embedding_vector(
        raw_vector(3.0, 4.0),
        input_index=7,
        task_type=EmbeddingTaskType.DOCUMENT,
    )

    assert vector.input_index == 7
    assert vector.task_type is EmbeddingTaskType.DOCUMENT
    assert vector.model == EMBEDDING_MODEL
    assert vector.dimensions == EMBEDDING_DIMENSIONS
    assert vector.values[:2] == pytest.approx((0.6, 0.8))
    assert "0.6" not in repr(vector)
    assert "0.8" not in repr(vector)


def test_vector_rejects_direct_construction_with_unnormalized_values() -> None:
    with pytest.raises(EmbeddingValidationError) as captured_error:
        EmbeddingVector(
            input_index=0,
            task_type=EmbeddingTaskType.DOCUMENT,
            values=tuple(float(value) for value in raw_vector(3.0, 4.0)),
        )

    assert captured_error.value.code is EmbeddingErrorCode.NOT_NORMALIZED


def test_vector_rejects_a_mutable_values_container() -> None:
    with pytest.raises(EmbeddingValidationError) as captured_error:
        EmbeddingVector(
            input_index=0,
            task_type=EmbeddingTaskType.DOCUMENT,
            values=[1.0] * EMBEDDING_DIMENSIONS,  # type: ignore[arg-type]
        )

    assert captured_error.value.code is EmbeddingErrorCode.NON_NUMERIC_VALUE


def test_vector_rejects_a_different_index_model() -> None:
    with pytest.raises(EmbeddingValidationError) as captured_error:
        create_embedding_vector(
            raw_vector(1.0),
            input_index=0,
            task_type=EmbeddingTaskType.DOCUMENT,
            model="different-model-marker",
        )

    assert captured_error.value.code is EmbeddingErrorCode.INVALID_MODEL
    assert "different-model-marker" not in str(captured_error.value)


def test_protocol_accepts_a_provider_independent_async_fake() -> None:
    class FakeGateway:
        async def embed(
            self,
            requests: tuple[EmbeddingRequest, ...],
            *,
            request_id: str,
        ) -> tuple[EmbeddingVector, ...]:
            assert request_id == "4b987954-6230-4f67-9c10-ecce963ddba9"
            return tuple(
                create_embedding_vector(
                    raw_vector(float(request.input_index + 1)),
                    input_index=request.input_index,
                    task_type=request.task_type,
                )
                for request in requests
            )

    gateway: EmbeddingGateway = FakeGateway()
    requests = (
        EmbeddingRequest(0, EmbeddingTaskType.DOCUMENT, "first"),
        EmbeddingRequest(1, EmbeddingTaskType.DOCUMENT, "second"),
    )

    vectors = asyncio.run(
        gateway.embed(requests, request_id="4b987954-6230-4f67-9c10-ecce963ddba9")
    )

    assert [vector.input_index for vector in vectors] == [0, 1]
