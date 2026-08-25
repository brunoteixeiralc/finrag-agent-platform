# Future Upload Threat Model

M2 has no upload endpoint, but its local pipeline treats every document and field as if it came from
an untrusted multipart request. This document records current controls and the controls still needed
before `POST /v1/documents` can be exposed.

## Protected assets

- API availability and bounded CPU/memory use;
- database integrity and corpus provenance;
- application secrets and internal network access;
- log confidentiality;
- trustworthy source citations and RAG behavior.

## Current controls

| Threat | M2 control | Residual risk or future control |
|---|---|---|
| Oversized upload | Raw bytes limited to 5 MiB before parsing | HTTP server must also cap streamed multipart bodies |
| Extension/MIME spoofing | Allowlist plus extension, MIME, and PDF signature agreement | Signature validation is not malware scanning |
| Path traversal | Filename reduced to a display-only basename and never opened as a path | Upload layer must continue using in-memory bytes or controlled temporary storage |
| Malformed PDF | Strict parser with generic content-safe errors | Keep `pypdf` patched and monitor parser advisories |
| PDF decompression/resource abuse | 50-page, 10 MiB decoded page-stream, and 500,000-character limits | Hard CPU preemption would require an isolated worker process |
| Encrypted or scanned PDF | Rejected; password handling and OCR are outside the MVP | Future OCR needs separate resource and accuracy evaluation |
| Active PDF content | JavaScript, links, actions, forms, attachments, and embedded files are not traversed or executed | Never serve original PDFs as trusted active content |
| Source URL SSRF | HTTP/HTTPS syntax stored as text; application never fetches the URL | Any future fetcher needs DNS/IP allowlisting and redirect controls |
| Metadata injection | Bounded JSON shape, key count, values, size, and reserved-key denylist | Encode output correctly in every future UI or export |
| Prompt injection | Preserved only as untrusted document content | RAG prompts must delimit evidence and prevent content from becoming system instructions |
| Sensitive-data leakage | Public/synthetic corpus policy and content-safe logs | Production upload needs classification, retention, and deletion policy |
| Partial processing | Result constructed only after every local stage succeeds | Embeddings and persistence must later use one atomic transaction boundary |
| Denial of service | Global 120-second deadline and cooperative cancellation | HTTP layer still needs authentication, rate limits, concurrency limits, and backpressure |
| Cross-site scripting | No document content is rendered by M2 | Future UI must escape citations and generated answers |
| Supply-chain compromise | Exact Python versions and commit-pinned GitHub Actions | Add dependency scanning and a regular update process |

## Logging rule

Processing logs may contain only validated request ID, SHA-256, normalized format, duration,
available counts, and terminal result. Raw bytes, text, filename, title, URL, metadata, credentials,
embedding vectors, and exception text are prohibited.

## Before enabling upload

The HTTP issue must add and test authentication, streamed size enforcement, multipart field limits,
content-type normalization, request cancellation, concurrency/rate controls, safe error mapping,
atomic embeddings plus persistence, and deletion/retention behavior. Malware scanning is a deployment
decision based on the threat environment, not functionality silently implied by M2.
