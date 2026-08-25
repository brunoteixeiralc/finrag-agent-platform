"""Deterministic structure-aware chunking without tokenization or external I/O."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import groupby

from app.ingestion.errors import DocumentValidationError, IngestionErrorCode
from app.ingestion.models import (
    ChunkDraft,
    ExtractedBlock,
    ExtractedBlockKind,
    ExtractedDocument,
    ExtractedPage,
)

TARGET_CHARACTERS = 1_800
MAX_CHARACTERS = 2_400
OVERLAP_CHARACTERS = 300
MINIMUM_FRAGMENT_CHARACTERS = 300
BLOCK_SEPARATOR = "\n\n"
SENTENCE_PATTERN = re.compile(r".+?(?:[.!?](?=\s|$)|$)", re.DOTALL)


@dataclass(frozen=True, slots=True)
class _RenderedChunk:
    content: str
    contains_table: bool


def chunk_document(document: ExtractedDocument) -> tuple[ChunkDraft, ...]:
    """Split one extracted document without crossing page or section boundaries."""

    rendered_chunks: list[tuple[_RenderedChunk, ExtractedPage, str | None]] = []
    for page in document.pages:
        for section, grouped_blocks in groupby(page.blocks, key=lambda block: block.section):
            blocks = tuple(grouped_blocks)
            rendered_chunks.extend((chunk, page, section) for chunk in _chunk_group(blocks))

    return tuple(
        ChunkDraft(
            chunk_index=index,
            content=rendered.content,
            character_count=len(rendered.content),
            page_index=page.page_index,
            page_label=page.page_label,
            section=section,
            contains_table=rendered.contains_table,
        )
        for index, (rendered, page, section) in enumerate(rendered_chunks)
    )


def _chunk_group(blocks: Sequence[ExtractedBlock]) -> tuple[_RenderedChunk, ...]:
    if not blocks:
        return ()

    heading = blocks[0].content if blocks[0].kind is ExtractedBlockKind.HEADING else None
    body_blocks = blocks[1:] if heading is not None else blocks
    _validate_heading(heading, has_body=bool(body_blocks))

    rendered: list[_RenderedChunk] = []
    general_blocks: list[ExtractedBlock] = []

    def flush_general_blocks() -> None:
        if general_blocks:
            rendered.extend(_chunk_general_blocks(general_blocks, heading))
            general_blocks.clear()

    for block in body_blocks:
        if block.kind is ExtractedBlockKind.TABLE:
            flush_general_blocks()
            rendered.extend(_chunk_table(block.content, heading))
        else:
            general_blocks.append(block)

    flush_general_blocks()
    if not rendered and heading is not None:
        rendered.append(_RenderedChunk(content=heading, contains_table=False))

    return tuple(rendered)


def _chunk_general_blocks(
    blocks: Sequence[ExtractedBlock],
    heading: str | None,
) -> tuple[_RenderedChunk, ...]:
    body_capacity = _body_capacity(heading)
    body_target = max(1, TARGET_CHARACTERS - _prefix_length(heading))
    bodies: list[str] = []
    short_blocks: list[str] = []

    def flush_short_blocks() -> None:
        if short_blocks:
            bodies.extend(_pack_short_blocks(short_blocks, body_target, body_capacity))
            short_blocks.clear()

    for block in blocks:
        content = block.content.strip()
        if not content:
            continue
        if len(content) <= body_capacity:
            short_blocks.append(content)
            continue
        flush_short_blocks()
        bodies.extend(_split_long_text(content, body_target, body_capacity))

    flush_short_blocks()
    return _render_general_bodies(bodies, heading)


def _pack_short_blocks(
    blocks: Sequence[str],
    target: int,
    maximum: int,
) -> tuple[str, ...]:
    packed: list[str] = []
    current = ""

    for block in blocks:
        candidate = block if not current else f"{current}{BLOCK_SEPARATOR}{block}"
        if current and len(candidate) > target:
            packed.append(current)
            current = block
        else:
            current = candidate
    if current:
        packed.append(current)

    return _merge_small_tail(packed, maximum, separator=BLOCK_SEPARATOR)


def _split_long_text(text: str, target: int, maximum: int) -> tuple[str, ...]:
    sentences = [match.group(0).strip() for match in SENTENCE_PATTERN.finditer(text)]
    fragments: list[str] = []
    for sentence in sentences:
        if len(sentence) <= maximum:
            fragments.append(sentence)
        else:
            fragments.extend(_hard_split(sentence, maximum))

    packed: list[str] = []
    current = ""
    for fragment in fragments:
        candidate = fragment if not current else f"{current} {fragment}"
        if current and len(candidate) > target:
            packed.append(current)
            current = fragment
        else:
            current = candidate
    if current:
        packed.append(current)

    return _merge_small_tail(packed, maximum, separator=" ")


def _hard_split(text: str, maximum: int) -> tuple[str, ...]:
    pieces: list[str] = []
    remaining = text.strip()
    while len(remaining) > maximum:
        split_at = remaining.rfind(" ", 0, maximum + 1)
        if split_at <= 0:
            split_at = maximum
        pieces.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        pieces.append(remaining)
    return tuple(pieces)


def _merge_small_tail(
    chunks: list[str],
    maximum: int,
    *,
    separator: str,
) -> tuple[str, ...]:
    if len(chunks) < 2 or len(chunks[-1]) >= MINIMUM_FRAGMENT_CHARACTERS:
        return tuple(chunks)

    merged = f"{chunks[-2]}{separator}{chunks[-1]}"
    if len(merged) <= maximum:
        chunks[-2:] = [merged]
    return tuple(chunks)


def _render_general_bodies(
    bodies: Sequence[str],
    heading: str | None,
) -> tuple[_RenderedChunk, ...]:
    rendered: list[_RenderedChunk] = []
    previous_body: str | None = None

    for body in bodies:
        components = [heading] if heading is not None else []
        base_length = len(BLOCK_SEPARATOR.join((*components, body)))
        overlap = ""
        if previous_body is not None:
            available = min(
                OVERLAP_CHARACTERS,
                MAX_CHARACTERS - base_length - len(BLOCK_SEPARATOR),
            )
            if available > 0:
                overlap = _select_overlap(previous_body, available)
        if overlap:
            components.append(overlap)
        components.append(body)
        content = BLOCK_SEPARATOR.join(components)
        rendered.append(_RenderedChunk(content=content, contains_table=False))
        previous_body = body

    return tuple(rendered)


def _select_overlap(text: str, maximum: int) -> str:
    sentences = [match.group(0).strip() for match in SENTENCE_PATTERN.finditer(text)]
    complete_sentences = [sentence for sentence in sentences if sentence[-1:] in {".", "!", "?"}]
    selected: list[str] = []
    for sentence in reversed(complete_sentences):
        candidate = " ".join((sentence, *selected))
        if len(candidate) > maximum:
            break
        selected.insert(0, sentence)
    if selected:
        return " ".join(selected)

    suffix = text[-maximum:].strip()
    first_space = suffix.find(" ")
    if first_space > 0 and len(text) > maximum:
        suffix = suffix[first_space + 1 :].lstrip()
    return suffix


def _chunk_table(table: str, heading: str | None) -> tuple[_RenderedChunk, ...]:
    body_capacity = _body_capacity(heading)
    body_target = max(1, TARGET_CHARACTERS - _prefix_length(heading))
    if len(table) <= body_capacity:
        return (_render_table(table, heading),)

    lines = table.splitlines()
    header = "\n".join(lines[:2])
    rows = lines[2:]
    if len(header) > body_capacity or not rows:
        _fail(
            IngestionErrorCode.CHUNK_TABLE_ROW_TOO_LARGE,
            "A table header or row exceeds the chunk limit.",
        )

    table_parts: list[str] = []
    current_rows: list[str] = []
    for row in rows:
        if len(f"{header}\n{row}") > body_capacity:
            _fail(
                IngestionErrorCode.CHUNK_TABLE_ROW_TOO_LARGE,
                "A table header or row exceeds the chunk limit.",
            )
        candidate_rows = [*current_rows, row]
        candidate = "\n".join((header, *candidate_rows))
        if current_rows and len(candidate) > body_target:
            table_parts.append("\n".join((header, *current_rows)))
            current_rows = [row]
        else:
            current_rows = candidate_rows
    if current_rows:
        table_parts.append("\n".join((header, *current_rows)))

    return tuple(_render_table(part, heading) for part in table_parts)


def _render_table(table: str, heading: str | None) -> _RenderedChunk:
    content = table if heading is None else f"{heading}{BLOCK_SEPARATOR}{table}"
    return _RenderedChunk(content=content, contains_table=True)


def _validate_heading(heading: str | None, *, has_body: bool) -> None:
    if heading is not None and (
        len(heading) > MAX_CHARACTERS or (has_body and _body_capacity(heading) <= 0)
    ):
        _fail(
            IngestionErrorCode.CHUNK_CONTEXT_TOO_LARGE,
            "A section heading leaves no room for chunk content.",
        )


def _body_capacity(heading: str | None) -> int:
    return MAX_CHARACTERS - _prefix_length(heading)


def _prefix_length(heading: str | None) -> int:
    return 0 if heading is None else len(heading) + len(BLOCK_SEPARATOR)


def _fail(code: IngestionErrorCode, message: str) -> None:
    raise DocumentValidationError(code, message, field="file")
