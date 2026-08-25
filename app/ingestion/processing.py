"""Atomic local orchestration for validation, extraction, and chunking."""

import asyncio
import logging
import math
from collections.abc import Mapping
from datetime import date
from time import perf_counter
from uuid import UUID

from app.ingestion.chunking import chunk_document
from app.ingestion.models import (
    ExtractedDocument,
    ProcessedDocument,
    ReceivedDocumentFile,
    SupportedMimeType,
    ValidatedDocumentInput,
)
from app.ingestion.pdf_extraction import extract_pdf_document
from app.ingestion.text_extraction import extract_text_document
from app.ingestion.validation import validate_document_input

DOCUMENT_PROCESSING_TIMEOUT_SECONDS = 120.0

logger = logging.getLogger(__name__)


class DocumentProcessingTimeoutError(TimeoutError):
    """Safe terminal error raised when the complete local deadline expires."""


async def process_document(
    file: ReceivedDocumentFile,
    *,
    request_id: str,
    title: str | None = None,
    source_name: str | None = None,
    source_url: str | None = None,
    published_at: str | date | None = None,
    metadata: str | Mapping[str, object] | None = None,
    timeout_seconds: float = DOCUMENT_PROCESSING_TIMEOUT_SECONDS,
) -> ProcessedDocument:
    """Run the local pipeline once and return a result only after every stage succeeds."""

    safe_request_id = _validate_request_id(request_id)
    safe_timeout = _validate_timeout(timeout_seconds)
    started_at = perf_counter()
    validated: ValidatedDocumentInput | None = None
    extracted: ExtractedDocument | None = None
    chunk_count: int | None = None
    deadline: asyncio.Timeout | None = None

    try:
        async with asyncio.timeout(safe_timeout) as active_deadline:
            deadline = active_deadline
            await _checkpoint()
            validated = validate_document_input(
                file,
                title=title,
                source_name=source_name,
                source_url=source_url,
                published_at=published_at,
                metadata=metadata,
            )
            await _checkpoint()
            extracted = _extract_document(validated)
            await _checkpoint()
            chunks = chunk_document(extracted)
            chunk_count = len(chunks)
            await _checkpoint()
            result = ProcessedDocument(
                original_filename=validated.original_filename,
                mime_type=validated.mime_type,
                sha256=validated.sha256,
                title=extracted.title,
                source_name=validated.source_name,
                source_url=validated.source_url,
                published_at=validated.published_at,
                metadata=validated.metadata,
                page_count=len(extracted.pages),
                character_count=extracted.character_count,
                chunks_count=chunk_count,
                chunks=chunks,
            )
    except TimeoutError as error:
        if deadline is None or not deadline.expired():
            _log_terminal_result(
                request_id=safe_request_id,
                result="failed",
                started_at=started_at,
                validated=validated,
                extracted=extracted,
                chunk_count=chunk_count,
            )
            raise
        _log_terminal_result(
            request_id=safe_request_id,
            result="timed_out",
            started_at=started_at,
            validated=validated,
            extracted=extracted,
            chunk_count=chunk_count,
        )
        raise DocumentProcessingTimeoutError(
            "The local document processing deadline was exceeded."
        ) from error
    except asyncio.CancelledError:
        _log_terminal_result(
            request_id=safe_request_id,
            result="cancelled",
            started_at=started_at,
            validated=validated,
            extracted=extracted,
            chunk_count=chunk_count,
        )
        raise
    except Exception:
        _log_terminal_result(
            request_id=safe_request_id,
            result="failed",
            started_at=started_at,
            validated=validated,
            extracted=extracted,
            chunk_count=chunk_count,
        )
        raise

    _log_terminal_result(
        request_id=safe_request_id,
        result="succeeded",
        started_at=started_at,
        validated=validated,
        extracted=extracted,
        chunk_count=chunk_count,
    )
    return result


def _extract_document(source: ValidatedDocumentInput) -> ExtractedDocument:
    if source.mime_type is SupportedMimeType.PDF:
        return extract_pdf_document(source)
    return extract_text_document(source)


async def _checkpoint() -> None:
    """Yield so caller cancellation and the operation deadline are observed between stages."""

    await asyncio.sleep(0)


def _validate_request_id(request_id: str) -> str:
    if not isinstance(request_id, str):
        raise ValueError("A canonical request ID is required.")
    try:
        parsed = UUID(request_id)
    except (ValueError, AttributeError) as error:
        raise ValueError("A canonical request ID is required.") from error
    if str(parsed) != request_id.lower():
        raise ValueError("A canonical request ID is required.")
    return request_id


def _validate_timeout(timeout_seconds: float) -> float:
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, int | float)
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
        or timeout_seconds > DOCUMENT_PROCESSING_TIMEOUT_SECONDS
    ):
        raise ValueError("The processing timeout must be between 0 and 120 seconds.")
    return float(timeout_seconds)


def _log_terminal_result(
    *,
    request_id: str,
    result: str,
    started_at: float,
    validated: ValidatedDocumentInput | None,
    extracted: ExtractedDocument | None,
    chunk_count: int | None,
) -> None:
    logger.info(
        "document_processing_finished",
        extra={
            "request_id": request_id,
            "document_sha256": validated.sha256 if validated is not None else None,
            "document_format": validated.mime_type.value if validated is not None else None,
            "duration_ms": round(max(0.0, perf_counter() - started_at) * 1_000, 3),
            "page_count": len(extracted.pages) if extracted is not None else None,
            "character_count": extracted.character_count if extracted is not None else None,
            "chunk_count": chunk_count,
            "result": result,
        },
    )
