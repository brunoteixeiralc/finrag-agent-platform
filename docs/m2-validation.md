# M2 Reproducible Validation

This guide reproduces the evidence used to close Milestone 2. No Gemini key, network call, or real
financial data is required for unit tests.

## Local quality checks

From the repository root with the virtual environment active:

```bash
ruff check .
ruff format --check .
python -m pytest -m "not integration"
python -m pip check
```

The committed Markdown, text, and PDF fixtures are exercised through the complete local pipeline by
`tests/test_document_fixtures.py`. Their expected SHA-256, page, and chunk counts are recorded in
[`tests/fixtures/documents/README.md`](../tests/fixtures/documents/README.md).

Run the content-safe measurement command directly:

```bash
python scripts/validate_documents.py \
  tests/fixtures/documents/synthetic_liquidity_report.md \
  tests/fixtures/documents/synthetic_credit_notes.txt \
  tests/fixtures/documents/synthetic_risk_report.pdf
```

The command prints only filename, SHA-256, format, page/character/chunk counts, and smallest/largest
chunk sizes. It never prints extracted content or metadata.

## PostgreSQL and pgvector integration

Start only the local database and run the isolated integration marker:

```bash
docker compose up -d --wait postgres
FINRAG_RUN_INTEGRATION=1 python -m pytest -m integration
docker compose stop postgres
```

Stopping the container preserves the local volume. CI uses `.env.example` placeholders, creates an
isolated service, and always removes its temporary containers and volume.

## Swagger and OpenAPI boundary

Start the API and open Swagger:

```bash
python -m uvicorn app.main:app --reload
```

- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI: <http://127.0.0.1:8000/openapi.json>

The schema must contain exactly `/health` and `/ready`. It must not contain `/v1/documents` or
`/v1/query`, because document upload, embeddings, persistence, retrieval, and generation are not
implemented.

## Manual validation with public BCB PDFs

Download the three public June 2026 Banco Central do Brasil reports to a temporary directory. Do not
commit them:

```bash
mkdir -p /tmp/finrag-bcb
curl -fsSL https://www.bcb.gov.br/content/ri/relatorioinflacao/202606/rpm202606b1p.pdf \
  -o /tmp/finrag-bcb/bcb_2026_projecoes_pib.pdf
curl -fsSL https://www.bcb.gov.br/content/ri/relatorioinflacao/202606/rpm202606b2p.pdf \
  -o /tmp/finrag-bcb/bcb_2026_projecoes_credito.pdf
curl -fsSL https://www.bcb.gov.br/content/ri/relatorioinflacao/202606/rpm202606b6p.pdf \
  -o /tmp/finrag-bcb/bcb_2026_risco_inflacao_atividade.pdf
```

Process them without displaying their content:

```bash
python scripts/validate_documents.py \
  /tmp/finrag-bcb/bcb_2026_projecoes_pib.pdf \
  /tmp/finrag-bcb/bcb_2026_projecoes_credito.pdf \
  /tmp/finrag-bcb/bcb_2026_risco_inflacao_atividade.pdf
```

Expected structural measurements for the exact source versions selected in M0:

| Document | SHA-256 | Pages | Characters | Chunks | Smallest | Largest |
|---|---|---:|---:|---:|---:|---:|
| GDP projections | `d9dadf82c320952f9651f530a24ff9c73efe0fc0d4d63d88e43170a53a73291d` | 2 | 6,387 | 4 | 1,355 | 2,046 |
| Credit projections | `07aa9e5a039977d892cc54f61c4798268884d2349ba793ac75bea0fb9d89ca6c` | 2 | 4,811 | 4 | 483 | 1,897 |
| Inflation and activity risk analysis | `3e912088fe102c84baa51f3a13ce461b0b8b0bcf1b5442db9bf4a4cfc940c260` | 5 | 14,504 | 10 | 495 | 2,014 |

The command also prints SHA-256 so a future run can distinguish a changed source file from a code
regression. Remove the temporary directory after validation if it is no longer needed.
