# Structure-Aware Chunking

M2-05 implements [ADR-003](adr/003-structure-aware-chunking.md) over the immutable structures
produced by the text and PDF extractors. The chunker is deterministic and local: it performs no
tokenization, filesystem, database, network, embedding, or LLM operation.

## Limits

| Setting | Value | Meaning |
|---|---:|---|
| Target | 1,800 characters | Preferred point for grouping content |
| Maximum | 2,400 characters | Hard limit including repeated context and overlap |
| Overlap | 300 characters | Maximum context copied from the preceding chunk |
| Minimum fragment | 300 characters | Small tails are merged when the boundary and maximum allow it |

The minimum is not a reason to cross a page or semantic section. A complete source boundary with
fewer than 300 characters remains a valid chunk.

## Boundary order

The algorithm processes content in this order:

1. document;
2. physical page;
3. semantic section;
4. structural block or paragraph;
5. sentence;
6. whitespace-aware hard split as the final fallback.

Chunk indexes are zero-based and global inside the document. Every `ChunkDraft` stores its exact
character count, page index and label when applicable, section, and `contains_table` flag.

Pages and sections are hard boundaries. Content and overlap never move across them, which keeps
future citations tied to a single source location. Repeated PDF headers and footers are currently
preserved because the MVP has no sufficiently reliable heuristic for removing them.

## Headings and overlap

The Markdown heading that starts a section is repeated at the beginning of every chunk from that
section. This repeated context is included in the 2,400-character maximum.

Overlap is added only between adjacent non-table chunks from the same page and section. It prefers
one or more complete trailing sentences and falls back to a word-bounded suffix. Available room is
calculated after the heading and new body are placed, so overlap can shrink or become zero but can
never make a chunk exceed the maximum.

## Tables

A Markdown table that fits remains intact in one chunk. When it exceeds the maximum, it is divided
only between data rows and its two-line header is repeated in every resulting chunk. Table chunks
do not receive ordinary text overlap.

If the heading plus table header and one indivisible row cannot fit, processing stops with the safe
`chunk_table_row_too_large` code. An oversized section heading similarly returns
`chunk_context_too_large`; neither error includes submitted content.

PDF tables are currently selectable text blocks because the PDF extractor does not infer visual
table structure. Adding layout or OCR interpretation would be a separate, evaluated capability.

## Validation with the BCB documents

The three public June 2026 Banco Central do Brasil PDFs were extracted and chunked without crossing
pages or exceeding 2,400 characters:

| Document | Pages | Chunks | Smallest | Largest |
|---|---:|---:|---:|---:|
| GDP projections | 2 | 4 | 1,355 | 2,046 |
| Credit projections | 2 | 4 | 483 | 1,897 |
| Inflation and activity risk analysis | 5 | 10 | 495 | 2,014 |

The PDFs remain outside Git. Their source links and extraction measurements are recorded in the
[PDF extraction documentation](pdf-extraction.md).

## Tests

Focused tests cover deterministic output, limits, small boundaries, sentence-aware splitting and
overlap, section isolation, page metadata, heading repetition, prompt injection, hard splitting,
whole tables, split tables, and safe errors:

```bash
python -m pytest tests/test_chunking.py
```
