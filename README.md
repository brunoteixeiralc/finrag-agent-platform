# FinRAG Agent Platform

FinRAG Agent Platform is a personal Applied AI portfolio project for building an
evidence-grounded Retrieval-Augmented Generation (RAG) API over public and synthetic
financial documents.

## Current status

Milestone **M2-03** adds deterministic Markdown and plain-text extraction to the tested foundation:

- FastAPI application;
- `GET /health` liveness endpoint;
- OpenAPI schema and Swagger UI;
- typed environment-based settings;
- secret-safe configuration values;
- PostgreSQL 17 with pgvector 0.8.6 through Docker Compose;
- automatic pgvector extension initialization;
- persistent local database storage and a container healthcheck;
- Psycopg 3 asynchronous connection pool managed by the FastAPI lifespan;
- `GET /ready` connectivity and pgvector check with a maximum two-second timeout;
- validated `X-Request-ID` propagation;
- uniform public error envelopes without internal details;
- constant-time Bearer API-key authentication for future `/v1` routes;
- CORS denied by default;
- reproducible API and PostgreSQL services through Docker Compose;
- minimal Python 3.14 application image running as a non-root user;
- automated tests with Pytest;
- linting and formatting with Ruff;
- GitHub Actions jobs for quality checks and isolated PostgreSQL + pgvector integration tests;
- M1 architecture and troubleshooting documentation;
- versioned `documents` and `chunks` tables with `vector(768)`, SHA-256 uniqueness, and cascade
  deletion;
- real database integration tests for schema invariants.
- immutable internal contracts for received files, extracted pages, extracted documents, and
  chunks without embeddings;
- local validation of the 5 MiB limit, filename, extension, MIME type, PDF signature, SHA-256,
  source fields, dates, and bounded metadata;
- stable ingestion error codes that do not expose rejected file content or metadata.
- UTF-8 and UTF-8 BOM decoding with normalized line endings and a 500,000-character limit;
- ordered structural blocks for headings, paragraphs, lists, tables, and frontmatter;
- hierarchical Markdown sections and deterministic title derivation;
- prompt injection preserved as untrusted document content, never executed as an instruction.

PDF extraction, chunking, persistence from the application, embeddings, retrieval, and answer
generation are planned but are not implemented yet.

## Requirements

- Python 3.14 (Docker and CI use 3.14.6)
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
| `FINRAG_API_PORT` | `8000` in local Compose | Not intended for production |
| `FINRAG_DB_USER` | Used by local Compose | Not intended for production |
| `FINRAG_DB_PASSWORD` | Used by local Compose | Not intended for production |
| `FINRAG_DB_NAME` | Used by local Compose | Not intended for production |
| `FINRAG_DB_PORT` | `5432` in local Compose | Not intended for production |
| `FINRAG_DATABASE_URL` | Not configured | Required |
| `FINRAG_READINESS_TIMEOUT_SECONDS` | `2` | Maximum `2` |

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

For a database volume created before M2-01, apply the document schema once without deleting local
data:

```bash
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U finrag -d finrag \
  -f /docker-entrypoint-initdb.d/002-create-document-schema.sql
```

New database volumes apply both versioned initialization files automatically. See the
[database schema documentation](docs/database-schema.md) before applying a migration manually.

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

## Run the complete stack with Docker

Build the API image and start both services:

```bash
docker compose up --build -d --wait
```

Compose waits for PostgreSQL to become healthy before starting the API. It then waits for the API
healthcheck before returning. Verify the services and endpoints:

```bash
docker compose ps
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready
```

Inspect logs or stop the stack while preserving database data:

```bash
docker compose logs api
docker compose logs postgres
docker compose down
```

The API container receives configuration at runtime from Compose. The image itself contains no
`.env`, tests, local virtual environment, database data, or API keys.

## Run the API without Docker

```bash
python -m uvicorn app.main:app --reload
```

The local endpoints are:

- API: <http://127.0.0.1:8000>
- Health: <http://127.0.0.1:8000/health>
- Readiness: <http://127.0.0.1:8000/ready>
- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI schema: <http://127.0.0.1:8000/openapi.json>

The health response is intentionally independent of external services:

```json
{
  "status": "ok"
}
```

Readiness checks PostgreSQL connectivity and the pgvector extension:

```json
{
  "status": "ready"
}
```

If the database is unavailable, unconfigured, times out, or does not have pgvector enabled,
`/ready` returns HTTP `503` with no connection details:

```json
{
  "status": "not_ready"
}
```

## HTTP and security conventions

Every response includes an `X-Request-ID` header. A canonical UUID supplied by the client is
preserved; missing or invalid values are replaced with a generated UUID. Future functional
responses under `/v1` will also include the same value in their JSON body.

Public errors use one envelope:

```json
{
  "error": {
    "code": "unauthorized",
    "message": "Authentication credentials are missing or invalid."
  },
  "request_id": "16c57582-d812-4ad7-aa07-4de17ca1b96c"
}
```

The Bearer dependency for `/v1` uses the configured `FINRAG_API_KEY` and timing-safe comparison.
No functional `/v1` route exists yet, so the production OpenAPI intentionally does not advertise
an unused security scheme. `/health`, `/ready`, `/docs`, and `/openapi.json` remain public. CORS is
not enabled; browser origins must be explicitly approved in a future requirement.

## Validate the project

Run the unit tests without Docker or network access:

```bash
python -m pytest -m "not integration"
```

Run the real PostgreSQL integration test after starting the Compose service:

```bash
FINRAG_RUN_INTEGRATION=1 python -m pytest -m integration
```

The integration test is skipped by default so unit tests remain independent of Docker.

Run linting and formatting checks:

```bash
ruff check .
ruff format --check .
```

The default `python -m pytest` command remains safe: integration tests require both the marker
selection and `FINRAG_RUN_INTEGRATION=1`, otherwise they are skipped.

## Continuous integration

The GitHub Actions workflow runs on every push and pull request, and can also be started manually.
It has read-only repository permissions and two independent jobs:

1. Ruff lint, Ruff format check, and unit tests without external services;
2. integration tests against an isolated PostgreSQL 17 + pgvector 0.8.6 container.

The workflow uses only committed local-development placeholders. It does not require or print a
Gemini key, production database URL, or other real secret. The integration job always removes its
temporary containers and volume.

## Documentation

- [M0 API contract](docs/api-contract-m0.md)
- [Architecture Decision Records](docs/adr/README.md)
- [M1 architecture](docs/architecture-m1.md)
- [Document database schema](docs/database-schema.md)
- [Document input validation](docs/document-input-validation.md)
- [Markdown and plain-text extraction](docs/text-extraction.md)
- [Troubleshooting](docs/troubleshooting.md)

The M0 documents define the intended MVP behavior. This README distinguishes implemented
features from planned work so that portfolio claims remain verifiable.

## Security baseline

- No real credentials or private financial data belong in this repository.
- Only public or synthetic documents will be used during the MVP.
- Local `.env` files are ignored by Git.
- Compose requires local database credentials from `.env`; the committed values are development
  placeholders only.
- The API image runs as the dedicated non-root UID/GID `10001`.
- `.dockerignore` excludes local configuration, tests, caches, Git history, and documentation from
  the image build context.
- No API key or database credential is passed as a Docker build argument or copied into the image.
- PostgreSQL binds to `127.0.0.1`, so it is not exposed on every host network interface.
- Secrets use masked Pydantic `SecretStr` values and are excluded from validation inputs.
- Production startup fails when the internal API key or database URL is absent.
- The liveness endpoint performs no external I/O and exposes no internal details.
- The readiness endpoint checks only PostgreSQL and pgvector, never Gemini.
- Database failures return only `{"status":"not_ready"}` without host, credentials, SQL, or
  stack traces.
- Invalid request IDs are never trusted or reflected.
- Rejected API keys and validation inputs are not echoed in responses.
- Supplied filenames are normalized for display only and never used as filesystem paths.
- Source URLs are validated and stored without making outbound requests.
- Frontmatter and prompt injection remain untrusted content and cannot change application behavior.
- Unexpected failures return a generic `internal_error` envelope.

## Next issue

M2-04 will extract textual PDFs while preserving page locations. Upload endpoints, embeddings,
retrieval, answer generation, agent behavior, observability, and cloud deployment remain later work
and must not be presented as implemented features.
