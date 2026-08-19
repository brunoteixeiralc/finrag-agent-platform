"""Unit tests for database readiness and application lifecycle."""

import asyncio
from dataclasses import dataclass
from typing import cast

from fastapi.testclient import TestClient
from psycopg_pool import AsyncConnectionPool

from app.database import POOL_CONNECTION_TIMEOUT_SECONDS, READINESS_QUERY, PsycopgDatabase
from app.main import create_app
from app.settings import Settings


@dataclass
class StubDatabase:
    """Controllable database gateway used by HTTP contract tests."""

    ready: bool
    delay_seconds: float = 0.0
    opened: bool = False
    closed: bool = False
    readiness_checks: int = 0

    async def open(self) -> None:
        self.opened = True

    async def close(self) -> None:
        self.closed = True

    async def is_ready(self) -> bool:
        self.readiness_checks += 1
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        return self.ready


class StubCursor:
    def __init__(self, row: tuple[bool] | None) -> None:
        self._row = row

    async def fetchone(self) -> tuple[bool] | None:
        return self._row


class StubConnection:
    def __init__(self, row: tuple[bool] | None) -> None:
        self._row = row
        self.query: str | None = None

    async def execute(self, query: str) -> StubCursor:
        self.query = query
        return StubCursor(self._row)


class StubConnectionContext:
    def __init__(self, connection: StubConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> StubConnection:
        return self._connection

    async def __aexit__(self, *_: object) -> None:
        return None


class StubPool:
    def __init__(self, row: tuple[bool] | None) -> None:
        self.connection_instance = StubConnection(row)
        self.connection_timeout: float | None = None

    def connection(self, *, timeout: float) -> StubConnectionContext:
        self.connection_timeout = timeout
        return StubConnectionContext(self.connection_instance)


def test_ready_returns_200_and_manages_database_lifecycle() -> None:
    database = StubDatabase(ready=True)
    settings = Settings(environment="test", _env_file=None)

    with TestClient(create_app(settings=settings, database=database)) as client:
        assert database.opened is True
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert database.closed is True


def test_ready_returns_safe_503_when_database_is_unavailable() -> None:
    database = StubDatabase(ready=False)
    settings = Settings(environment="test", _env_file=None)

    with TestClient(create_app(settings=settings, database=database)) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


def test_health_does_not_check_database_readiness() -> None:
    database = StubDatabase(ready=False)
    settings = Settings(environment="test", _env_file=None)

    with TestClient(create_app(settings=settings, database=database)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert database.readiness_checks == 0


def test_ready_enforces_configured_timeout() -> None:
    database = StubDatabase(ready=True, delay_seconds=0.05)
    settings = Settings(
        environment="test",
        readiness_timeout_seconds=0.01,
        _env_file=None,
    )

    with TestClient(create_app(settings=settings, database=database)) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


def test_psycopg_probe_requires_pgvector_extension() -> None:
    pool = StubPool(row=(False,))
    database = PsycopgDatabase(
        "postgresql://unused",
        pool=cast(AsyncConnectionPool, pool),
    )

    is_ready = asyncio.run(database.is_ready())

    assert is_ready is False
    assert pool.connection_timeout == POOL_CONNECTION_TIMEOUT_SECONDS
    assert pool.connection_instance.query == READINESS_QUERY


def test_psycopg_probe_accepts_enabled_pgvector_extension() -> None:
    pool = StubPool(row=(True,))
    database = PsycopgDatabase(
        "postgresql://unused",
        pool=cast(AsyncConnectionPool, pool),
    )

    assert asyncio.run(database.is_ready()) is True
