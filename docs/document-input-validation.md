# Document Input Validation

M2-02 introduces local contracts and validation for untrusted files before any extraction,
chunking, embedding call, or database write. The validator performs no filesystem or network I/O.

## Internal flow

```text
ReceivedDocumentFile
        |
        v
validate size, name, extension, MIME, signature, and fields
        |
        v
ValidatedDocumentInput + deterministic SHA-256
        |
        v
text extractor or PDF extractor -> ExtractedDocument
        |
        v
future chunker -> ChunkDraft
```

The contracts are frozen, slotted dataclasses. `ChunkDraft` intentionally has no embedding because
the embedding provider is not part of M2.

## File rules

| Extension | Normalized MIME type | Content check |
|---|---|---|
| `.md` | `text/markdown` | no NUL bytes |
| `.txt` | `text/plain` | no NUL bytes |
| `.pdf` | `application/pdf` | starts with `%PDF-` |

- The maximum raw size is 5 MiB, measured from the actual bytes.
- SHA-256 is calculated over those original bytes.
- MIME parameters such as `charset=utf-8` are removed before comparison.
- Text decoding and empty-whitespace detection belong to M2-03.
- PDF parsing, page limits, and selectable-text checks are performed by the M2-04 extractor after
  this initial byte-level validation.

## Filename handling

The supplied filename is untrusted display metadata. Both `/` and `\` path prefixes are removed,
Unicode is normalized, and control characters are replaced. The resulting name is never opened,
joined to a directory, or otherwise used as a filesystem path.

## Optional fields

- `title` and `source_name` are trimmed, Unicode-normalized, reject control characters, and have a
  200-character limit.
- `published_at` accepts a date object or the exact `YYYY-MM-DD` representation.
- `source_url` requires an HTTP or HTTPS scheme and a hostname. It is stored as text and never
  accessed, including when it points to localhost or a private address.

## Metadata

Metadata must be a JSON object or an equivalent mapping with:

- a maximum canonical UTF-8 size of 4 KiB;
- at most 20 keys;
- non-empty keys without control characters, unique after trimming;
- primitive values or lists of at most 20 primitive values;
- finite numbers only;
- no nested objects or nested lists;
- no platform-controlled keys such as `id`, `status`, `sha256`, `chunks_count`, or `created_at`.

## Safe errors

`DocumentValidationError` exposes a stable `IngestionErrorCode` and an optional field name for
future HTTP translation. Its message never includes file bytes, submitted metadata, URLs, or other
rejected values.

Run the focused tests without Docker or network access:

```bash
python -m pytest tests/test_document_input_validation.py
```
