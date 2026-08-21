"""Local document ingestion contracts and validation."""

from app.ingestion.errors import DocumentValidationError, IngestionErrorCode
from app.ingestion.models import (
    ChunkDraft,
    ExtractedDocument,
    ExtractedPage,
    ReceivedDocumentFile,
    SupportedMimeType,
    ValidatedDocumentInput,
)
from app.ingestion.validation import validate_document_input

__all__ = [
    "ChunkDraft",
    "DocumentValidationError",
    "ExtractedDocument",
    "ExtractedPage",
    "IngestionErrorCode",
    "ReceivedDocumentFile",
    "SupportedMimeType",
    "ValidatedDocumentInput",
    "validate_document_input",
]
