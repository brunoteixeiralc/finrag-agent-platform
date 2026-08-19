# FinRAG Agent Platform

FinRAG Agent Platform is a personal Applied AI portfolio project for building an
evidence-grounded Retrieval-Augmented Generation (RAG) API over public and synthetic
financial documents.

## Current status

Milestone **M1-02** provides the executable API and configuration foundation:

- FastAPI application;
- `GET /health` liveness endpoint;
- OpenAPI schema and Swagger UI;
- typed environment-based settings;
- secret-safe configuration values;
- automated tests with Pytest;
- linting and formatting with Ruff.

Document ingestion, PostgreSQL, pgvector, embeddings, retrieval, and answer generation are
planned but are not implemented yet.

## Requirements

- Python 3.14
- `pip`

No running database, Docker service, Gemini API key, or network access is required for this
milestone.

## Local setup

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Copy the configuration example if you want to override development defaults:

```bash
cp .env.example .env
```

All environment variables use the `FINRAG_` prefix. The current settings are:

| Variable | Development default | Production |
|---|---|---|
| `FINRAG_APP_NAME` | `FinRAG Agent Platform` | Optional |
| `FINRAG_ENVIRONMENT` | `development` | Set to `production` |
| `FINRAG_API_KEY` | Not configured | Required |
| `FINRAG_DATABASE_URL` | Not configured | Required |

The example values are placeholders. Never store real secrets in `.env.example` or Git.

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
- Secrets use masked Pydantic `SecretStr` values and are excluded from validation inputs.
- Production startup fails when the internal API key or database URL is absent.
- The liveness endpoint performs no external I/O and exposes no internal details.

## Next issue

M1-03 will add a local PostgreSQL service with pgvector through Docker Compose. The application
will connect to it in M1-04.
