# Markdown and Plain-Text Extraction

M2-03 converts a validated Markdown or plain-text input into deterministic structured text. The
extractor is local, uses only the Python standard library, and performs no filesystem, database,
network, or LLM operation.

## Output model

Each text document produces one logical `ExtractedPage` with `page_index=None`. The page keeps the
complete normalized content for auditing and an ordered sequence of blocks for future chunking:

- `frontmatter`;
- `heading` with its level and hierarchical section;
- `paragraph`;
- `list`;
- `table`.

Physical page indexes remain reserved for the PDF extractor in M2-04.

## Normalization and limits

- UTF-8 and UTF-8 with BOM are accepted.
- CRLF and CR line endings become LF.
- Other content is not rewritten or interpreted.
- Empty and whitespace-only documents are rejected.
- Invalid UTF-8 is rejected with a content-safe error.
- Normalized text is limited to 500,000 characters.

The title supplied during validation takes precedence. Otherwise, Markdown uses its first ATX
heading (`#` through `######`), and documents without one use the normalized filename stem.

## Structure rules

- A heading updates the section associated with subsequent blocks.
- Nested headings produce paths such as `Annual Report > Key Metrics`.
- Lists and Markdown tables remain ordered blocks with their original text.
- Markdown inside fenced code blocks is not interpreted as headings or lists.
- The normalized full text remains available even though blank separator lines are not blocks.

This is deliberately a small structural parser, not a complete Markdown renderer. It preserves the
features needed by the chunking ADR without adding a Markdown dependency to the MVP.

## Untrusted content

Frontmatter is preserved as a `frontmatter` block and is not merged into trusted request metadata.
Prompt injections, URLs, HTML, code, and sentences that resemble instructions remain ordinary
document content. The extractor never executes or follows them.

## Safe errors

Extraction reuses `DocumentValidationError` with stable codes for invalid encoding, empty text,
excessive character count, invalid derived title, and unsupported MIME type. Error messages never
contain submitted text or bytes.

Run the focused tests without Docker or network access:

```bash
python -m pytest tests/test_text_extraction.py
```
