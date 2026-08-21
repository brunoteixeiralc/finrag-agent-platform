"""Immutable internal contracts for the document processing pipeline."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

type MetadataPrimitive = str | int | float | bool | None
type MetadataValue = MetadataPrimitive | tuple[MetadataPrimitive, ...]


class SupportedMimeType(StrEnum):
    """File types accepted by the MVP."""

    MARKDOWN = "text/markdown"
    PLAIN_TEXT = "text/plain"
    PDF = "application/pdf"


class ExtractedBlockKind(StrEnum):
    """Structural block types preserved for deterministic chunking."""

    FRONTMATTER = "frontmatter"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"


@dataclass(frozen=True, slots=True)
class ReceivedDocumentFile:
    """Untrusted file values received before extraction."""

    filename: str
    mime_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class ValidatedDocumentInput:
    """Validated input that is safe to pass to a format-specific extractor."""

    original_filename: str
    mime_type: SupportedMimeType
    content: bytes
    sha256: str
    title: str | None
    source_name: str | None
    source_url: str | None
    published_at: date | None
    metadata: Mapping[str, MetadataValue]


@dataclass(frozen=True, slots=True)
class ExtractedBlock:
    """One ordered content block associated with its Markdown section."""

    kind: ExtractedBlockKind
    content: str
    section: str | None
    heading_level: int | None = None


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    """One extracted page or text unit with source location information."""

    page_index: int | None
    content: str
    blocks: tuple[ExtractedBlock, ...]
    page_label: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    """Deterministic structured text produced by a format-specific extractor."""

    source: ValidatedDocumentInput
    title: str
    pages: tuple[ExtractedPage, ...]
    character_count: int


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    """Chunk before the embedding provider is called."""

    chunk_index: int
    content: str
    character_count: int
    page_index: int | None = None
    page_label: str | None = None
    section: str | None = None
    contains_table: bool = False
