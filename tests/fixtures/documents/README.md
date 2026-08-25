# Synthetic Document Fixtures

These files are intentionally small, public-safe, and entirely fictional. They exist only to make
the M2 validation, extraction, and chunking pipeline reproducible in unit tests.

- `synthetic_liquidity_report.md` covers headings, paragraphs, a Markdown table, provenance text,
  and an inert prompt-injection sentence.
- `synthetic_credit_notes.txt` covers ordered plain-text paragraphs.
- `synthetic_risk_report.pdf` covers two textual PDF pages with narrative and aggregate synthetic
  metrics.

The fixtures contain no code, architecture, prompts, customer data, credentials, or business
information from Act Digital, Sicoob, Itau, Banco Central do Brasil, or any other organization.
The PDF is a committed test input, not a project deliverable or financial report.

Expected deterministic processing results:

| Fixture | SHA-256 | Pages | Chunks |
|---|---|---:|---:|
| `synthetic_liquidity_report.md` | `b6d5256af535cde1b96cdf0bccdefda0954c63bf61a8d4549ca8827cd6cb0dc0` | 1 | 4 |
| `synthetic_credit_notes.txt` | `b834437fbcadfc929214ad888a97c43f06e2d411efc532543912d649b9f0222b` | 1 | 1 |
| `synthetic_risk_report.pdf` | `db607d8ec92922379599ee666b6e91402b2ffd3bcbcc3d77c2570415f55384e7` | 2 | 2 |
