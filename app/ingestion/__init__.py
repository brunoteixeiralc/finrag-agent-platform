"""Local document ingestion contracts and validation."""

from app.ingestion.errors import DocumentValidationError, IngestionErrorCode
from app.ingestion.models import (
    ChunkDraft,
    ExtractedBlock,
    ExtractedBlockKind,
    ExtractedDocument,
    ExtractedPage,
    ReceivedDocumentFile,
    SupportedMimeType,
    ValidatedDocumentInput,
)
from app.ingestion.pdf_extraction import extract_pdf_document
from app.ingestion.text_extraction import extract_text_document
from app.ingestion.validation import validate_document_input

__all__ = [
    "ChunkDraft",
    "DocumentValidationError",
    "ExtractedBlock",
    "ExtractedBlockKind",
    "ExtractedDocument",
    "ExtractedPage",
    "IngestionErrorCode",
    "ReceivedDocumentFile",
    "SupportedMimeType",
    "ValidatedDocumentInput",
    "extract_pdf_document",
    "extract_text_document",
    "validate_document_input",
]
