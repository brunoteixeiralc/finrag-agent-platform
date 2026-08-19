"""Async PostgreSQL access used by infrastructure readiness checks."""

from typing import Protocol

from psycopg import Error
from psycopg_pool import AsyncConnectionPool

READINESS_QUERY = """
SELECT EXISTS (
    SELECT 1
    FROM pg_extension
    WHERE extname = 'vector'
)
"""
POOL_CONNECTION_TIMEOUT_SECONDS = 2.0


class DatabaseGateway(Protocol):
    """Minimal database contract required by the HTTP application."""

    async def open(self) -> None:
        """Open resources needed by the gateway."""

    async def close(self) -> None:
        """Release resources held by the gateway."""

    async def is_ready(self) -> bool:
        """Return whether PostgreSQL and pgvector are available."""


class UnconfiguredDatabase:
    """Gateway used when no database URL is configured."""

    async def open(self) -> None:
        """No resources are needed without database configuration."""

    async def close(self) -> None:
        """No resources are held without database configuration."""

    async def is_ready(self) -> bool:
        """An unconfigured database is never ready."""

        return False


class PsycopgDatabase:
    """Psycopg async connection pool with a pgvector readiness probe."""

    def __init__(
        self,
        conninfo: str,
        *,
        pool: AsyncConnectionPool | None = None,
    ) -> None:
        self._pool = (
            pool
            if pool is not None
            else AsyncConnectionPool(
                conninfo=conninfo,
                min_size=1,
                max_size=5,
                timeout=POOL_CONNECTION_TIMEOUT_SECONDS,
                open=False,
                name="finrag-database",
            )
        )

    async def open(self) -> None:
        """Start the pool without making API startup depend on PostgreSQL."""

        await self._pool.open(wait=False)

    async def close(self) -> None:
        """Close all connections managed by the pool."""

        await self._pool.close()

    async def is_ready(self) -> bool:
        """Check connectivity and confirm that pgvector is enabled."""

        try:
            async with self._pool.connection(timeout=POOL_CONNECTION_TIMEOUT_SECONDS) as connection:
                cursor = await connection.execute(READINESS_QUERY)
                row = await cursor.fetchone()
        except Error:
            return False

        return bool(row and row[0])
