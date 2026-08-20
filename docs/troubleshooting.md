# Troubleshooting

These checks cover the local M1 environment. Run commands from the repository root.

## `curl` cannot connect and Swagger does not open

Nothing is listening on port `8000`. Start the full stack:

```bash
docker compose up --build -d --wait
docker compose ps
```

Or, when running the API outside Docker, activate the virtual environment and start Uvicorn:

```bash
source .venv/bin/activate
python -m uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000/docs> or call `curl -i http://127.0.0.1:8000/health`.

## Docker is unavailable

Start Docker Desktop and wait until its engine is ready. Confirm it with:

```bash
docker version
docker compose version
```

If either command cannot reach the daemon, the API can still run without Docker, but `/ready`
will return `503` until PostgreSQL is configured and available.

## Port `8000` or `5432` is already in use

Identify the process or container using the port:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:5432 -sTCP:LISTEN
docker compose ps
```

Stop the conflicting process, or override the local host port in `.env` with
`FINRAG_API_PORT` or `FINRAG_DB_PORT`. Container-to-container traffic continues to use port `5432`.

## `/health` is healthy but `/ready` returns `503`

This is expected when PostgreSQL is unavailable, the database URL is wrong, or pgvector is not
enabled. Inspect the service and extension:

```bash
docker compose ps
docker compose logs postgres
docker compose exec postgres psql -U finrag -d finrag \
  -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

The public readiness response deliberately omits connection details and stack traces.

## Integration tests are skipped

Start PostgreSQL and opt in explicitly:

```bash
docker compose up -d --wait postgres
FINRAG_RUN_INTEGRATION=1 python -m pytest -m integration
```

The guard prevents an accidental connection to an external database during the default unit-test
run.

## Reset the local database

First stop services without losing data:

```bash
docker compose down
```

Only when a clean database is intentional, remove the named volume:

```bash
docker compose down --volumes
```

The second command permanently deletes the local PostgreSQL data stored by this Compose project.
