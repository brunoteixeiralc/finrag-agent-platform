# FinRAG Agent Platform

FinRAG Agent Platform is a personal Applied AI portfolio project for building an
evidence-grounded Retrieval-Augmented Generation (RAG) API over public and synthetic
financial documents.

## Current status

Milestone **M1-03** provides the executable API and local database foundation:

- FastAPI application;
- `GET /health` liveness endpoint;
- OpenAPI schema and Swagger UI;
- typed environment-based settings;
- secret-safe configuration values;
- PostgreSQL 17 with pgvector 0.8.6 through Docker Compose;
- automatic pgvector extension initialization;
- persistent local database storage and a container healthcheck;
- automated tests with Pytest;
- linting and formatting with Ruff.

Application database connections, document ingestion, embeddings, retrieval, and answer
generation are planned but are not implemented yet.

## Requirements

- Python 3.14
- `pip`
- Docker Desktop or another Docker Engine with Compose

No Gemini API key is required for this milestone.

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
| `FINRAG_DB_USER` | Used by local Compose | Not intended for production |
| `FINRAG_DB_PASSWORD` | Used by local Compose | Not intended for production |
| `FINRAG_DB_NAME` | Used by local Compose | Not intended for production |
| `FINRAG_DB_PORT` | `5432` in local Compose | Not intended for production |
| `FINRAG_DATABASE_URL` | Not configured | Required |

The example values are local-only placeholders. Never store real or production secrets in
`.env.example` or Git. Keep `FINRAG_DATABASE_URL` synchronized with the four local database
variables when overriding them.

## Run the local database

Create `.env` from the development example, then start PostgreSQL:

```bash
cp .env.example .env
docker compose up -d --wait postgres
```

Check the database and pgvector extension:

```bash
docker compose exec postgres psql -U finrag -d finrag -c "SELECT 1;"
docker compose exec postgres psql -U finrag -d finrag \
  -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

Inspect the service or stop it without deleting data:

```bash
docker compose ps
docker compose logs postgres
docker compose down
```

The Compose volume `finrag_postgres_data` (created by Docker as
`finrag-agent-platform_finrag_postgres_data`) preserves local data across container restarts and
`docker compose down`. Delete it only when you intentionally want a clean local database:

```bash
docker compose down --volumes
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
- Compose requires local database credentials from `.env`; the committed values are development
  placeholders only.
- PostgreSQL binds to `127.0.0.1`, so it is not exposed on every host network interface.
- Secrets use masked Pydantic `SecretStr` values and are excluded from validation inputs.
- Production startup fails when the internal API key or database URL is absent.
- The liveness endpoint performs no external I/O and exposes no internal details.

## Next issue

M1-04 will connect the FastAPI application to PostgreSQL and add a dependency-aware `/ready`
endpoint.
