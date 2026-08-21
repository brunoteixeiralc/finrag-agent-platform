"""Unit tests for local, content-safe document input validation."""

import hashlib
from datetime import date

import pytest

from app.ingestion import (
    DocumentValidationError,
    IngestionErrorCode,
    ReceivedDocumentFile,
    SupportedMimeType,
    validate_document_input,
)
from app.ingestion.validation import MAX_FILE_SIZE_BYTES


def received_file(
    *,
    filename: str = "report.md",
    mime_type: str = "text/markdown",
    content: bytes = b"# Quarterly report\n\nRevenue increased.",
) -> ReceivedDocumentFile:
    return ReceivedDocumentFile(filename=filename, mime_type=mime_type, content=content)


@pytest.mark.parametrize(
    ("file", "expected_mime_type"),
    [
        (received_file(), SupportedMimeType.MARKDOWN),
        (
            received_file(
                filename="notes.txt",
                mime_type="text/plain; charset=utf-8",
                content=b"Public financial notes.",
            ),
            SupportedMimeType.PLAIN_TEXT,
        ),
        (
            received_file(
                filename="statement.PDF",
                mime_type="application/pdf",
                content=b"%PDF-1.7\nsynthetic test fixture\n%%EOF",
            ),
            SupportedMimeType.PDF,
        ),
    ],
)
def test_supported_document_types_are_accepted(
    file: ReceivedDocumentFile,
    expected_mime_type: SupportedMimeType,
) -> None:
    validated = validate_document_input(file)

    assert validated.mime_type is expected_mime_type
    assert validated.sha256 == hashlib.sha256(file.content).hexdigest()


def test_sha256_is_deterministic_for_the_original_bytes() -> None:
    file = received_file(content=b"same bytes every time")

    first = validate_document_input(file)
    second = validate_document_input(file)

    assert first.sha256 == second.sha256
    assert first.content == file.content


def test_filename_is_reduced_to_a_safe_display_name() -> None:
    posix = validate_document_input(received_file(filename="../../reports/report.md"))
    windows = validate_document_input(received_file(filename=r"C:\uploads\report.md"))
    control = validate_document_input(received_file(filename="report\n.md"))

    assert posix.original_filename == "report.md"
    assert windows.original_filename == "report.md"
    assert control.original_filename == "report_.md"


def test_file_larger_than_five_mib_is_rejected() -> None:
    file = received_file(content=b"x" * (MAX_FILE_SIZE_BYTES + 1))

    with pytest.raises(DocumentValidationError) as captured_error:
        validate_document_input(file)

    assert captured_error.value.code is IngestionErrorCode.FILE_TOO_LARGE


@pytest.mark.parametrize(
    ("file", "expected_code"),
    [
        (received_file(content=b""), IngestionErrorCode.EMPTY_FILE),
        (received_file(filename="report.exe"), IngestionErrorCode.UNSUPPORTED_FILE_EXTENSION),
        (
            received_file(mime_type="application/octet-stream"),
            IngestionErrorCode.UNSUPPORTED_MIME_TYPE,
        ),
        (
            received_file(mime_type="application/pdf"),
            IngestionErrorCode.FILE_TYPE_MISMATCH,
        ),
        (
            received_file(
                filename="report.pdf",
                mime_type="application/pdf",
                content=b"This is not a PDF.",
            ),
            IngestionErrorCode.FILE_TYPE_MISMATCH,
        ),
        (
            received_file(filename="report.txt", mime_type="text/plain", content=b"a\x00b"),
            IngestionErrorCode.UNSAFE_FILE_CONTENT,
        ),
    ],
)
def test_incompatible_or_unsafe_files_are_rejected(
    file: ReceivedDocumentFile,
    expected_code: IngestionErrorCode,
) -> None:
    with pytest.raises(DocumentValidationError) as captured_error:
        validate_document_input(file)

    assert captured_error.value.code is expected_code
    assert captured_error.value.field == "file"


def test_optional_contract_fields_are_normalized_and_validated() -> None:
    validated = validate_document_input(
        received_file(),
        title="  Quarterly results  ",
        source_name="  Banco Central do Brasil  ",
        source_url="https://www.bcb.gov.br/publicacoes/",
        published_at="2026-06-25",
    )

    assert validated.title == "Quarterly results"
    assert validated.source_name == "Banco Central do Brasil"
    assert validated.source_url == "https://www.bcb.gov.br/publicacoes/"
    assert validated.published_at == date(2026, 6, 25)


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("title", "x" * 201, IngestionErrorCode.INVALID_TITLE),
        ("title", "unsafe\ntitle", IngestionErrorCode.INVALID_TITLE),
        ("source_name", "x" * 201, IngestionErrorCode.INVALID_SOURCE_NAME),
        ("source_name", "unsafe\rsource", IngestionErrorCode.INVALID_SOURCE_NAME),
    ],
)
def test_invalid_text_fields_are_rejected(
    field: str,
    value: str,
    expected_code: IngestionErrorCode,
) -> None:
    with pytest.raises(DocumentValidationError) as captured_error:
        validate_document_input(received_file(), **{field: value})  # type: ignore[arg-type]

    assert captured_error.value.code is expected_code


def test_http_source_url_is_stored_without_being_accessed() -> None:
    source_url = "http://127.0.0.1:1/private-document"

    validated = validate_document_input(received_file(), source_url=source_url)

    assert validated.source_url == source_url


@pytest.mark.parametrize("source_url", ["ftp://example.com/report", "https:///missing-host"])
def test_non_http_or_malformed_source_url_is_rejected(source_url: str) -> None:
    with pytest.raises(DocumentValidationError) as captured_error:
        validate_document_input(received_file(), source_url=source_url)

    assert captured_error.value.code is IngestionErrorCode.INVALID_SOURCE_URL


@pytest.mark.parametrize("published_at", ["25-06-2026", "2026-02-30", "20260625"])
def test_invalid_published_at_is_rejected(published_at: str) -> None:
    with pytest.raises(DocumentValidationError) as captured_error:
        validate_document_input(received_file(), published_at=published_at)

    assert captured_error.value.code is IngestionErrorCode.INVALID_PUBLISHED_AT


def test_simple_metadata_and_short_lists_are_accepted() -> None:
    validated = validate_document_input(
        received_file(),
        metadata='{"external_id":"BCB-2026","reviewed":true,"quarters":[1,2,3,4]}',
    )

    assert validated.metadata == {
        "external_id": "BCB-2026",
        "quarters": (1, 2, 3, 4),
        "reviewed": True,
    }


def test_metadata_cannot_exceed_twenty_keys() -> None:
    metadata = {f"key_{index}": index for index in range(21)}

    with pytest.raises(DocumentValidationError) as captured_error:
        validate_document_input(received_file(), metadata=metadata)

    assert captured_error.value.code is IngestionErrorCode.METADATA_TOO_MANY_KEYS


def test_metadata_cannot_exceed_four_kib() -> None:
    metadata = {"notes": "x" * 4096}

    with pytest.raises(DocumentValidationError) as captured_error:
        validate_document_input(received_file(), metadata=metadata)

    assert captured_error.value.code is IngestionErrorCode.METADATA_TOO_LARGE


@pytest.mark.parametrize("reserved_key", ["id", "sha256", "STATUS", "chunks_count", "created_at"])
def test_metadata_cannot_override_reserved_fields(reserved_key: str) -> None:
    with pytest.raises(DocumentValidationError) as captured_error:
        validate_document_input(received_file(), metadata={reserved_key: "override"})

    assert captured_error.value.code is IngestionErrorCode.METADATA_RESERVED_KEY


def test_metadata_keys_cannot_collide_after_normalization() -> None:
    with pytest.raises(DocumentValidationError) as captured_error:
        validate_document_input(received_file(), metadata={"region": "BR", " region ": "US"})

    assert captured_error.value.code is IngestionErrorCode.INVALID_METADATA


@pytest.mark.parametrize(
    "metadata",
    [
        "not-json",
        '{"region":"BR","region":"US"}',
        '{"unsafe\\nkey":"value"}',
    ],
)
def test_invalid_or_ambiguous_metadata_json_is_rejected(metadata: str) -> None:
    with pytest.raises(DocumentValidationError) as captured_error:
        validate_document_input(received_file(), metadata=metadata)

    assert captured_error.value.code is IngestionErrorCode.INVALID_METADATA


@pytest.mark.parametrize(
    "metadata",
    [
        ["not", "an", "object"],
        {"nested": {"objects": "are not accepted"}},
        {"nested": [["lists"]]},
        {"too_many_items": list(range(21))},
        {"not_finite": float("nan")},
    ],
)
def test_complex_metadata_values_are_rejected(metadata: object) -> None:
    with pytest.raises(DocumentValidationError) as captured_error:
        validate_document_input(received_file(), metadata=metadata)  # type: ignore[arg-type]

    assert captured_error.value.code is IngestionErrorCode.INVALID_METADATA


def test_errors_do_not_echo_rejected_content_or_metadata() -> None:
    secret = "sensitive-metadata-value-that-must-not-leak"

    with pytest.raises(DocumentValidationError) as captured_error:
        validate_document_input(received_file(), metadata={"nested": {"secret": secret}})

    error = captured_error.value
    assert error.code is IngestionErrorCode.INVALID_METADATA
    assert secret not in str(error)
    assert secret not in repr(error)
