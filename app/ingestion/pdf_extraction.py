"""Safe, deterministic extraction of textual PDF pages."""

import re
import unicodedata
from io import BytesIO
from pathlib import PurePosixPath

from pypdf import PdfReader

from app.ingestion.errors import DocumentValidationError, IngestionErrorCode
from app.ingestion.models import (
    ExtractedBlock,
    ExtractedBlockKind,
    ExtractedDocument,
    ExtractedPage,
    SupportedMimeType,
    ValidatedDocumentInput,
)
from app.ingestion.text_extraction import MAX_EXTRACTED_CHARACTERS
from app.ingestion.validation import MAX_TITLE_CHARACTERS

MAX_PDF_PAGES = 50
MAX_PDF_PAGE_CONTENT_STREAM_BYTES = 10 * 1024 * 1024
PARAGRAPH_SEPARATOR_PATTERN = re.compile(r"\n[ \t]*\n+")


def extract_pdf_document(source: ValidatedDocumentInput) -> ExtractedDocument:
    """Extract textual pages without accessing active or embedded PDF content."""

    if source.mime_type is not SupportedMimeType.PDF:
        _fail(
            IngestionErrorCode.UNSUPPORTED_EXTRACTION_TYPE,
            "This extractor supports only PDF documents.",
        )

    try:
        return _extract_pdf_document(source)
    except DocumentValidationError:
        raise
    except Exception as error:
        raise DocumentValidationError(
            IngestionErrorCode.PDF_MALFORMED,
            "The PDF structure is invalid or unsupported.",
            field="file",
        ) from error


def _extract_pdf_document(source: ValidatedDocumentInput) -> ExtractedDocument:
    reader = PdfReader(BytesIO(source.content), strict=True)
    if reader.is_encrypted:
        _fail(
            IngestionErrorCode.PDF_ENCRYPTED,
            "Encrypted PDF documents are not supported.",
        )

    page_count = len(reader.pages)
    if page_count == 0:
        _fail(IngestionErrorCode.PDF_MALFORMED, "The PDF contains no pages.")
    if page_count > MAX_PDF_PAGES:
        _fail(
            IngestionErrorCode.PDF_PAGE_LIMIT_EXCEEDED,
            "The PDF exceeds the 50-page limit.",
        )

    page_labels = _explicit_page_labels(reader, page_count)
    extracted_pages: list[ExtractedPage] = []
    total_character_count = 0

    for page_offset, page in enumerate(reader.pages):
        contents = page.get_contents()
        if contents is not None and len(contents.get_data()) > MAX_PDF_PAGE_CONTENT_STREAM_BYTES:
            _fail(
                IngestionErrorCode.PDF_CONTENT_STREAM_TOO_LARGE,
                "A PDF page exceeds the safe content-stream limit.",
            )

        extracted_text = page.extract_text()
        normalized_text = _normalize_page_text(extracted_text or "")
        if not normalized_text:
            _fail(
                IngestionErrorCode.PDF_OCR_UNSUPPORTED,
                "Every PDF page must contain selectable text; OCR is not supported.",
            )

        total_character_count += len(normalized_text)
        if total_character_count > MAX_EXTRACTED_CHARACTERS:
            _fail(
                IngestionErrorCode.EXTRACTED_TEXT_TOO_LARGE,
                "The extracted text exceeds the 500,000 character limit.",
            )

        extracted_pages.append(
            ExtractedPage(
                page_index=page_offset + 1,
                page_label=page_labels[page_offset],
                content=normalized_text,
                blocks=_page_blocks(normalized_text),
            )
        )

    return ExtractedDocument(
        source=source,
        title=_resolve_pdf_title(source),
        pages=tuple(extracted_pages),
        character_count=total_character_count,
    )


def _explicit_page_labels(reader: PdfReader, page_count: int) -> tuple[str | None, ...]:
    if "/PageLabels" not in reader.root_object:
        return (None,) * page_count

    labels = reader.page_labels
    if len(labels) != page_count:
        _fail(IngestionErrorCode.PDF_MALFORMED, "The PDF page labels are invalid.")

    normalized_labels: list[str | None] = []
    for label in labels:
        normalized = unicodedata.normalize("NFKC", str(label)).strip()
        contains_control = any(
            unicodedata.category(character) in {"Cc", "Cf"} for character in normalized
        )
        if not normalized or len(normalized) > 50 or contains_control:
            _fail(IngestionErrorCode.PDF_MALFORMED, "The PDF page labels are invalid.")
        normalized_labels.append(normalized)
    return tuple(normalized_labels)


def _normalize_page_text(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(" ".join(line.split()) for line in normalized.split("\n")).strip()


def _page_blocks(content: str) -> tuple[ExtractedBlock, ...]:
    raw_blocks = [block.strip() for block in PARAGRAPH_SEPARATOR_PATTERN.split(content)]
    return tuple(
        ExtractedBlock(
            kind=ExtractedBlockKind.PARAGRAPH,
            content=block,
            section=None,
        )
        for block in raw_blocks
        if block
    )


def _resolve_pdf_title(source: ValidatedDocumentInput) -> str:
    if source.title is not None:
        return source.title

    stem = PurePosixPath(source.original_filename).stem.replace("_", " ").replace("-", " ")
    title = " ".join(stem.split())
    if not title or len(title) > MAX_TITLE_CHARACTERS:
        _fail(IngestionErrorCode.INVALID_TITLE, "A valid document title could not be derived.")
    return title


def _fail(code: IngestionErrorCode, message: str) -> None:
    raise DocumentValidationError(code, message, field="file")
