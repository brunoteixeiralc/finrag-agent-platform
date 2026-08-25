# Textual PDF Extraction

M2-04 converts a validated textual PDF into deterministic page-scoped content for future chunking.
It operates only on the bytes already held in memory and performs no filesystem, database, network,
OCR, or LLM operation.

## Dependency and output

The implementation uses `pypdf==6.16.1`, the only runtime dependency added by this issue. Every
accepted document produces one ordered `ExtractedPage` per physical PDF page:

- `page_index` starts at 1 and identifies the physical page;
- `page_label` is populated only when the PDF declares valid explicit page-label metadata;
- `content` contains normalized selectable text;
- paragraph blocks remain inside their originating page and never cross page boundaries.

The document title supplied during input validation takes precedence. Otherwise, it is derived
deterministically from the normalized filename.

## Normalization and limits

- CRLF and CR line endings become LF.
- Horizontal whitespace inside each line is collapsed for stable, readable text.
- Every page must contain selectable text; image-only pages are rejected because OCR is outside
  the MVP.
- A PDF can contain at most 50 pages.
- Extracted text is limited to 500,000 characters across the complete document.
- A decoded page content stream is limited to 10 MiB before text extraction.

## Untrusted PDF behavior

The reader uses strict parsing and never attempts to decrypt a document. The extraction path reads
only pages, page-label metadata, content streams, and selectable text. It does not access or execute
links, JavaScript, open actions, attachments, forms, or embedded files.

Page labels are normalized and rejected when empty, over 50 characters, or containing control
characters. They remain source location metadata and are never interpreted as instructions.

Malformed, encrypted, image-only, oversized, and unsupported files return stable internal error
codes through `DocumentValidationError`. Public HTTP translation will be added with the upload
endpoint; rejected content and parser internals must never appear in a response.

## Public-document validation

The extractor was manually checked against the three June 2026 Banco Central do Brasil reports
selected for the MVP. These public source files remain outside Git:

| Document | Physical pages | Extracted characters | Page blocks |
|---|---:|---:|---:|
| [GDP projections](https://www.bcb.gov.br/content/ri/relatorioinflacao/202606/rpm202606b1p.pdf) | 2 | 6,387 | 9 |
| [Credit projections](https://www.bcb.gov.br/content/ri/relatorioinflacao/202606/rpm202606b2p.pdf) | 2 | 4,811 | 7 |
| [Inflation and activity risk analysis](https://www.bcb.gov.br/content/ri/relatorioinflacao/202606/rpm202606b6p.pdf) | 5 | 14,504 | 9 |

The files contain no explicit PDF page-label metadata, so `page_label` is `None`; their printed
report page numbers remain part of the extracted text. This distinction prevents the application
from inventing source metadata that the file did not declare.

## Tests

Focused tests generate synthetic fixtures in memory and cover page ordering, page isolation,
explicit labels, title precedence, deterministic output, ignored active content, encryption,
malformed structure, image-only content, page limits, content-stream and character limits, and MIME
routing:

```bash
python -m pytest tests/test_pdf_extraction.py
```
