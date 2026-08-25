# Local Document Processing

M2-06 composes validation, format-specific extraction, and structure-aware chunking into one
asynchronous use case. It still performs no persistence, embedding, network, database, or LLM
operation and does not expose a new HTTP endpoint.

## Flow

```text
ReceivedDocumentFile + optional source fields
        |
        v
validate bytes, type, metadata, and SHA-256
        |
        v
route Markdown/text or PDF extractor
        |
        v
ExtractedDocument
        |
        v
structure-aware chunking
        |
        v
ProcessedDocument
```

The final result is constructed only after every stage succeeds. It contains the normalized
filename, format, SHA-256, title, validated provenance, page and character counts, chunk count, and
all `ChunkDraft` values. It intentionally excludes the original raw bytes and intermediate page
contents.

If validation, extraction, or chunking fails, the original safe exception is propagated and no
partial `ProcessedDocument` is returned. There is no retry because all work is deterministic and
local.

## Deadline and cancellation

The complete local operation has a default and maximum deadline of 120 seconds, matching ADR-004.
The timeout can be reduced by the caller for tests or a smaller request budget, but cannot exceed
the global ingestion limit.

The orchestration yields at explicit checkpoints before and after each synchronous stage. This
makes caller cancellation and the deadline observable without leaving a worker thread or task
running in the background. Cancellation is propagated as `asyncio.CancelledError`; timeout becomes
the safe `DocumentProcessingTimeoutError`.

The parser itself is not preempted in the middle of a synchronous call. Its work is bounded instead
by the existing 5 MiB file, 50-page PDF, 10 MiB decoded page-stream, and 500,000-character limits.
A future workload requiring hard preemption of CPU-bound parsing would need an isolated worker
process, which is unnecessary for this MVP.

## Safe observability

Exactly one terminal `document_processing_finished` log is emitted after processing starts. Its
structured fields are limited to:

- validated `request_id`;
- document SHA-256 and normalized format, when validation reached them;
- duration in milliseconds;
- page, character, and chunk counts available at the terminal stage;
- `succeeded`, `failed`, `timed_out`, or `cancelled` result.

Logs never include raw bytes, extracted content, filename, title, source name, URL, metadata,
exception text, or stack trace. The SHA-256 supports correlation and deduplication without logging
the document itself.

## Example

```python
result = await process_document(
    ReceivedDocumentFile(
        filename="report.md",
        mime_type="text/markdown",
        content=b"# Public Report\n\nEvidence.",
    ),
    request_id="4b987954-6230-4f67-9c10-ecce963ddba9",
)
```

The function receives the already validated request ID that the HTTP middleware will eventually
provide. Invalid or non-canonical IDs are rejected before processing so they cannot inject data into
logs.

## Tests

Focused tests cover full Markdown and PDF processing, deterministic results, atomic failure,
single-attempt behavior, global timeout, caller cancellation, bounded configuration, canonical
request IDs, and success/failure log redaction:

```bash
python -m pytest tests/test_document_processing.py
```
