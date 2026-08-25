"""Unit tests for atomic local document processing orchestration."""

import asyncio
import hashlib
import logging
from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

import app.ingestion.processing as processing_module
from app.ingestion import (
    DocumentProcessingTimeoutError,
    DocumentValidationError,
    IngestionErrorCode,
    ReceivedDocumentFile,
    SupportedMimeType,
    process_document,
)

REQUEST_ID = "4b987954-6230-4f67-9c10-ecce963ddba9"


def textual_pdf_bytes(text: str) -> bytes:
    """Create one textual PDF page without adding a fixture dependency."""

    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)
    page = writer.add_blank_page(width=612, height=792)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_reference})}
    )
    stream = DecodedStreamObject()
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def markdown_file(content: str = "# Report\n\nRevenue increased.") -> ReceivedDocumentFile:
    return ReceivedDocumentFile(
        filename="report.md",
        mime_type="text/markdown",
        content=content.encode(),
    )


def run_processing(
    file: ReceivedDocumentFile,
    **fields: object,
):
    return asyncio.run(process_document(file, request_id=REQUEST_ID, **fields))


def test_markdown_runs_the_complete_local_pipeline() -> None:
    content = "# Annual Report\n\nRevenue increased.\n\nCosts decreased."

    result = run_processing(
        markdown_file(content),
        source_name="Synthetic corpus",
        source_url="https://example.com/report",
        published_at="2026-08-25",
        metadata={"year": 2026},
    )

    assert result.mime_type is SupportedMimeType.MARKDOWN
    assert result.sha256 == hashlib.sha256(content.encode()).hexdigest()
    assert result.title == "Annual Report"
    assert result.page_count == 1
    assert result.character_count == len(content)
    assert result.chunks_count == len(result.chunks) == 1
    assert result.chunks[0].content.startswith("# Annual Report")
    assert result.metadata == {"year": 2026}
    assert not hasattr(result, "source")


def test_pdf_runs_the_complete_local_pipeline() -> None:
    content = textual_pdf_bytes("Public financial evidence")
    file = ReceivedDocumentFile(
        filename="report.pdf",
        mime_type="application/pdf",
        content=content,
    )

    result = run_processing(file, title="BCB report")

    assert result.mime_type is SupportedMimeType.PDF
    assert result.title == "BCB report"
    assert result.page_count == 1
    assert result.chunks_count == 1
    assert result.chunks[0].page_index == 1
    assert "Public financial evidence" in result.chunks[0].content


def test_same_input_produces_the_same_complete_result() -> None:
    file = markdown_file("# Report\n\nDeterministic evidence.")

    first = run_processing(file)
    second = run_processing(file)

    assert first == second


def test_validation_failure_never_returns_a_partial_result(
    caplog: pytest.LogCaptureFixture,
) -> None:
    file = ReceivedDocumentFile(
        filename="report.pdf",
        mime_type="application/pdf",
        content=b"%PDF-1.7\nsensitive-but-malformed",
    )

    with (
        caplog.at_level(logging.INFO, logger=processing_module.logger.name),
        pytest.raises(DocumentValidationError) as captured_error,
    ):
        run_processing(file)

    assert captured_error.value.code is IngestionErrorCode.PDF_MALFORMED
    assert [record.result for record in caplog.records] == ["failed"]
    assert "sensitive-but-malformed" not in caplog.text


def test_failed_stage_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = 0

    def fail_extraction(*_: object) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("sensitive internal failure")

    monkeypatch.setattr(processing_module, "_extract_document", fail_extraction)

    with (
        caplog.at_level(logging.INFO, logger=processing_module.logger.name),
        pytest.raises(RuntimeError),
    ):
        run_processing(markdown_file())

    assert calls == 1
    assert [record.result for record in caplog.records] == ["failed"]
    assert "sensitive internal failure" not in caplog.text


def test_stage_timeout_is_not_misclassified_as_the_global_deadline(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail_extraction(*_: object) -> None:
        raise TimeoutError("stage timeout marker")

    monkeypatch.setattr(processing_module, "_extract_document", fail_extraction)

    with (
        caplog.at_level(logging.INFO, logger=processing_module.logger.name),
        pytest.raises(TimeoutError) as captured_error,
    ):
        run_processing(markdown_file())

    assert type(captured_error.value) is TimeoutError
    assert [record.result for record in caplog.records] == ["failed"]
    assert "stage timeout marker" not in caplog.text


def test_timeout_stops_before_a_result_is_constructed(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    checkpoint_calls = 0

    async def delayed_after_validation() -> None:
        nonlocal checkpoint_calls
        checkpoint_calls += 1
        if checkpoint_calls == 2:
            await asyncio.sleep(0.02)
        else:
            await asyncio.sleep(0)

    monkeypatch.setattr(processing_module, "_checkpoint", delayed_after_validation)

    with (
        caplog.at_level(logging.INFO, logger=processing_module.logger.name),
        pytest.raises(DocumentProcessingTimeoutError),
    ):
        run_processing(markdown_file(), timeout_seconds=0.001)

    assert checkpoint_calls == 2
    assert [record.result for record in caplog.records] == ["timed_out"]
    assert caplog.records[0].document_sha256 is not None
    assert caplog.records[0].page_count is None
    assert caplog.records[0].chunk_count is None


def test_caller_cancellation_is_propagated_without_a_result(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    validation_finished = asyncio.Event()
    checkpoint_calls = 0

    async def wait_after_validation() -> None:
        nonlocal checkpoint_calls
        checkpoint_calls += 1
        if checkpoint_calls == 2:
            validation_finished.set()
            await asyncio.Event().wait()
        await asyncio.sleep(0)

    async def scenario() -> None:
        task = asyncio.create_task(process_document(markdown_file(), request_id=REQUEST_ID))
        await validation_finished.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    monkeypatch.setattr(processing_module, "_checkpoint", wait_after_validation)

    with caplog.at_level(logging.INFO, logger=processing_module.logger.name):
        asyncio.run(scenario())

    assert [record.result for record in caplog.records] == ["cancelled"]
    assert caplog.records[0].document_sha256 is not None
    assert caplog.records[0].page_count is None


def test_success_log_contains_only_safe_processing_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_content = "Confidential marker that must not be logged."
    secret_metadata = "private-metadata-marker"
    secret_url = "https://example.com/private-url-marker"
    file = markdown_file(f"# Report\n\n{secret_content}")

    with caplog.at_level(logging.INFO, logger=processing_module.logger.name):
        result = run_processing(
            file,
            source_name="private-source-marker",
            source_url=secret_url,
            metadata={"note": secret_metadata},
        )

    assert result.chunks_count == 1
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.request_id == REQUEST_ID
    assert record.document_sha256 == result.sha256
    assert record.document_format == "text/markdown"
    assert record.page_count == 1
    assert record.character_count == result.character_count
    assert record.chunk_count == 1
    assert record.result == "succeeded"
    serialized_record = repr(record.__dict__)
    assert secret_content not in serialized_record
    assert secret_metadata not in serialized_record
    assert secret_url not in serialized_record
    assert "private-source-marker" not in serialized_record


@pytest.mark.parametrize(
    "timeout_seconds",
    [0, -1, 120.1, float("inf"), float("nan"), True],
)
def test_timeout_must_be_positive_finite_and_within_global_limit(
    timeout_seconds: float,
) -> None:
    with pytest.raises(ValueError, match="between 0 and 120 seconds"):
        run_processing(markdown_file(), timeout_seconds=timeout_seconds)


@pytest.mark.parametrize("request_id", ["invalid", "", "{" + "x" * 100])
def test_request_id_must_be_a_canonical_uuid(request_id: str) -> None:
    with pytest.raises(ValueError, match="canonical request ID"):
        asyncio.run(process_document(markdown_file(), request_id=request_id))
