# FinRAG Agent Platform

FinRAG Agent Platform is a personal Applied AI portfolio project for building an
evidence-grounded Retrieval-Augmented Generation (RAG) API over public and synthetic
financial documents.

## Current status

Milestone **M1-01** provides only the executable API foundation:

- FastAPI application;
- `GET /health` liveness endpoint;
- OpenAPI schema and Swagger UI;
- automated tests with Pytest;
- linting and formatting with Ruff.

Document ingestion, PostgreSQL, pgvector, embeddings, retrieval, and answer generation are
planned but are not implemented yet.

## Requirements

- Python 3.14
- `pip`

No database, Docker service, Gemini API key, or network access is required for this milestone.

## Local setup

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run the API

```bash
python -m uvicorn app.main:app --reload
```

The local endpoints are:

- API: <http://127.0.0.1:8000>
- Health: <http://127.0.0.1:8000/health>
- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI schema: <http://127.0.0.1:8000/openapi.json>

The health response is intentionally independent of external services:

```json
{
  "status": "ok"
}
```

## Validate the project

Run the tests:

```bash
python -m pytest
```

Run linting and formatting checks:

```bash
ruff check .
ruff format --check .
```

## Documentation

- [M0 API contract](docs/api-contract-m0.md)
- [Architecture Decision Records](docs/adr/README.md)

The M0 documents define the intended MVP behavior. This README distinguishes implemented
features from planned work so that portfolio claims remain verifiable.

## Security baseline

- No real credentials or private financial data belong in this repository.
- Only public or synthetic documents will be used during the MVP.
- Local `.env` files are ignored by Git.
- The liveness endpoint performs no external I/O and exposes no internal details.

## Next issue

M1-02 will add typed application settings and secret-handling rules. Database and pgvector
support arrive in later M1 issues.
