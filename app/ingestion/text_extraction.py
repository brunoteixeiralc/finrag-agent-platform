"""Deterministic extraction of UTF-8 Markdown and plain-text documents."""

import re
from pathlib import PurePosixPath

from app.ingestion.errors import DocumentValidationError, IngestionErrorCode
from app.ingestion.models import (
    ExtractedBlock,
    ExtractedBlockKind,
    ExtractedDocument,
    ExtractedPage,
    SupportedMimeType,
    ValidatedDocumentInput,
)
from app.ingestion.validation import MAX_TITLE_CHARACTERS

MAX_EXTRACTED_CHARACTERS = 500_000

ATX_HEADING_PATTERN = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
LIST_ITEM_PATTERN = re.compile(r"^[ \t]*(?:[-+*]|\d+[.)])[ \t]+\S")
TABLE_DELIMITER_CELL_PATTERN = re.compile(r"^:?-{3,}:?$")
FENCE_PATTERN = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def extract_text_document(source: ValidatedDocumentInput) -> ExtractedDocument:
    """Decode and structure one validated Markdown or plain-text document without I/O."""

    if source.mime_type not in {SupportedMimeType.MARKDOWN, SupportedMimeType.PLAIN_TEXT}:
        _fail(
            IngestionErrorCode.UNSUPPORTED_EXTRACTION_TYPE,
            "This extractor supports only Markdown and plain-text documents.",
        )

    try:
        decoded = source.content.decode("utf-8-sig")
    except UnicodeDecodeError:
        _fail(
            IngestionErrorCode.INVALID_TEXT_ENCODING,
            "The document must use valid UTF-8 encoding.",
        )

    normalized = decoded.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        _fail(
            IngestionErrorCode.EMPTY_EXTRACTED_TEXT,
            "The extracted document contains no text.",
        )
    if len(normalized) > MAX_EXTRACTED_CHARACTERS:
        _fail(
            IngestionErrorCode.EXTRACTED_TEXT_TOO_LARGE,
            "The extracted text exceeds the 500,000 character limit.",
        )

    if source.mime_type is SupportedMimeType.MARKDOWN:
        blocks, first_heading = _extract_markdown_blocks(normalized)
    else:
        blocks = _extract_plain_text_blocks(normalized)
        first_heading = None

    title = _resolve_title(source, first_heading)
    page = ExtractedPage(page_index=None, content=normalized, blocks=blocks)
    return ExtractedDocument(
        source=source,
        title=title,
        pages=(page,),
        character_count=len(normalized),
    )


def _extract_markdown_blocks(
    content: str,
) -> tuple[tuple[ExtractedBlock, ...], str | None]:
    raw_blocks = _split_markdown_blocks(content)
    extracted: list[ExtractedBlock] = []
    heading_path: list[str] = []
    first_heading: str | None = None

    for raw_block, is_frontmatter in raw_blocks:
        heading = ATX_HEADING_PATTERN.fullmatch(raw_block) if not is_frontmatter else None
        if heading is not None:
            level = len(heading.group(1))
            heading_text = heading.group(2).strip()
            heading_path = heading_path[: level - 1]
            heading_path.extend([""] * (level - 1 - len(heading_path)))
            heading_path.append(heading_text)
            section = " > ".join(part for part in heading_path if part)
            first_heading = first_heading or heading_text
            extracted.append(
                ExtractedBlock(
                    kind=ExtractedBlockKind.HEADING,
                    content=raw_block,
                    section=section,
                    heading_level=level,
                )
            )
            continue

        section = " > ".join(part for part in heading_path if part) or None
        extracted.append(
            ExtractedBlock(
                kind=(
                    ExtractedBlockKind.FRONTMATTER
                    if is_frontmatter
                    else _classify_content_block(raw_block)
                ),
                content=raw_block,
                section=section,
            )
        )

    return tuple(extracted), first_heading


def _split_markdown_blocks(content: str) -> tuple[tuple[str, bool], ...]:
    lines = content.split("\n")
    blocks: list[tuple[str, bool]] = []
    start_index = 0

    if lines and lines[0].strip() == "---":
        closing_index = next(
            (index for index in range(1, len(lines)) if lines[index].strip() in {"---", "..."}),
            None,
        )
        if closing_index is not None:
            blocks.append(("\n".join(lines[: closing_index + 1]), True))
            start_index = closing_index + 1

    buffer: list[str] = []
    active_fence: str | None = None

    def flush_buffer() -> None:
        if buffer:
            blocks.append(("\n".join(buffer), False))
            buffer.clear()

    for line in lines[start_index:]:
        fence = FENCE_PATTERN.match(line)
        if active_fence is not None:
            buffer.append(line)
            if fence is not None:
                marker = fence.group(1)
                if marker[0] == active_fence[0] and len(marker) >= len(active_fence):
                    active_fence = None
            continue

        if fence is not None:
            flush_buffer()
            active_fence = fence.group(1)
            buffer.append(line)
            continue

        if ATX_HEADING_PATTERN.fullmatch(line) is not None:
            flush_buffer()
            blocks.append((line, False))
            continue

        if not line.strip():
            flush_buffer()
            continue

        buffer.append(line)

    flush_buffer()
    return tuple(blocks)


def _extract_plain_text_blocks(content: str) -> tuple[ExtractedBlock, ...]:
    return tuple(
        ExtractedBlock(
            kind=_classify_content_block(raw_block),
            content=raw_block,
            section=None,
        )
        for raw_block in _split_on_blank_lines(content)
    )


def _split_on_blank_lines(content: str) -> tuple[str, ...]:
    blocks: list[str] = []
    buffer: list[str] = []
    for line in content.split("\n"):
        if line.strip():
            buffer.append(line)
        elif buffer:
            blocks.append("\n".join(buffer))
            buffer.clear()
    if buffer:
        blocks.append("\n".join(buffer))
    return tuple(blocks)


def _classify_content_block(content: str) -> ExtractedBlockKind:
    lines = content.split("\n")
    if _is_markdown_table(lines):
        return ExtractedBlockKind.TABLE
    if LIST_ITEM_PATTERN.match(lines[0]) is not None:
        return ExtractedBlockKind.LIST
    return ExtractedBlockKind.PARAGRAPH


def _is_markdown_table(lines: list[str]) -> bool:
    if len(lines) < 2 or "|" not in lines[0] or "|" not in lines[1]:
        return False
    delimiter_cells = [cell.strip() for cell in lines[1].strip().strip("|").split("|")]
    return bool(delimiter_cells) and all(
        TABLE_DELIMITER_CELL_PATTERN.fullmatch(cell) is not None for cell in delimiter_cells
    )


def _resolve_title(source: ValidatedDocumentInput, first_heading: str | None) -> str:
    if source.title is not None:
        return source.title

    fallback = PurePosixPath(source.original_filename).stem.replace("_", " ").replace("-", " ")
    title = first_heading or " ".join(fallback.split())
    if not title or len(title) > MAX_TITLE_CHARACTERS:
        _fail(IngestionErrorCode.INVALID_TITLE, "A valid document title could not be derived.")
    return title


def _fail(code: IngestionErrorCode, message: str) -> None:
    raise DocumentValidationError(code, message, field="file")
