"""Integration test for PostgreSQL and pgvector readiness."""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


@pytest.mark.integration
def test_ready_with_real_postgresql_and_pgvector() -> None:
    if os.getenv("FINRAG_RUN_INTEGRATION") != "1":
        pytest.skip("set FINRAG_RUN_INTEGRATION=1 to run PostgreSQL integration tests")

    settings = Settings(environment="test")
    if settings.database_url is None:
        pytest.fail("FINRAG_DATABASE_URL is required for integration tests")

    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
