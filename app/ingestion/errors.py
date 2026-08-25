"""Stable, content-safe errors for document ingestion."""

from enum import StrEnum


class IngestionErrorCode(StrEnum):
    """Machine-readable failures for future translation to HTTP errors."""

    EMPTY_FILE = "empty_file"
    FILE_TOO_LARGE = "file_too_large"
    INVALID_FILENAME = "invalid_filename"
    UNSUPPORTED_FILE_EXTENSION = "unsupported_file_extension"
    UNSUPPORTED_MIME_TYPE = "unsupported_mime_type"
    FILE_TYPE_MISMATCH = "file_type_mismatch"
    UNSAFE_FILE_CONTENT = "unsafe_file_content"
    INVALID_TITLE = "invalid_title"
    INVALID_SOURCE_NAME = "invalid_source_name"
    INVALID_SOURCE_URL = "invalid_source_url"
    INVALID_PUBLISHED_AT = "invalid_published_at"
    INVALID_METADATA = "invalid_metadata"
    METADATA_TOO_LARGE = "metadata_too_large"
    METADATA_TOO_MANY_KEYS = "metadata_too_many_keys"
    METADATA_RESERVED_KEY = "metadata_reserved_key"
    INVALID_TEXT_ENCODING = "invalid_text_encoding"
    EMPTY_EXTRACTED_TEXT = "empty_extracted_text"
    EXTRACTED_TEXT_TOO_LARGE = "extracted_text_too_large"
    UNSUPPORTED_EXTRACTION_TYPE = "unsupported_extraction_type"
    PDF_MALFORMED = "pdf_malformed"
    PDF_ENCRYPTED = "pdf_encrypted"
    PDF_PAGE_LIMIT_EXCEEDED = "pdf_page_limit_exceeded"
    PDF_OCR_UNSUPPORTED = "pdf_ocr_unsupported"
    PDF_CONTENT_STREAM_TOO_LARGE = "pdf_content_stream_too_large"
    CHUNK_CONTEXT_TOO_LARGE = "chunk_context_too_large"
    CHUNK_TABLE_ROW_TOO_LARGE = "chunk_table_row_too_large"


class DocumentValidationError(ValueError):
    """Validation failure that never includes rejected values or file content."""

    def __init__(
        self,
        code: IngestionErrorCode,
        message: str,
        *,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.field = field
