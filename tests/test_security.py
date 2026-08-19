"""Isolated tests for the future `/v1` Bearer authentication dependency."""

from collections.abc import Iterator

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from app.http import REQUEST_ID_HEADER, RequestIdMiddleware, register_error_handlers
from app.security import require_api_key
from app.settings import Settings

TEST_API_KEY = "test-only-api-key-never-use-in-production"


def create_security_test_app(api_key: str | None = TEST_API_KEY) -> FastAPI:
    """Create a test-only route without adding endpoints to production."""

    application = FastAPI()
    application.state.settings = Settings(
        environment="test",
        api_key=api_key,
        _env_file=None,
    )
    application.add_middleware(RequestIdMiddleware)
    register_error_handlers(application)

    @application.get("/v1/protected", dependencies=[Depends(require_api_key)])
    async def protected_route(request: Request) -> dict[str, str]:
        return {"request_id": request.state.request_id}

    return application


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_security_test_app()) as test_client:
        yield test_client


@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer invalid-key", f"Basic {TEST_API_KEY}"],
)
def test_missing_or_invalid_api_key_returns_safe_401(
    client: TestClient,
    authorization: str | None,
) -> None:
    headers = {"Authorization": authorization} if authorization is not None else {}

    response = client.get("/v1/protected", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Authentication credentials are missing or invalid.",
        },
        "request_id": response.headers[REQUEST_ID_HEADER],
    }
    assert TEST_API_KEY not in response.text


def test_valid_api_key_allows_request(client: TestClient) -> None:
    response = client.get(
        "/v1/protected",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
    )

    assert response.status_code == 200
    assert response.json()["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_unconfigured_api_key_rejects_request() -> None:
    with TestClient(create_security_test_app(api_key=None)) as client:
        response = client.get(
            "/v1/protected",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 401
    assert TEST_API_KEY not in response.text


def test_security_scheme_is_documented_only_when_dependency_is_used(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert schema["components"]["securitySchemes"]["BearerAuth"] == {
        "type": "http",
        "description": "Internal API key required by functional `/v1` endpoints.",
        "scheme": "bearer",
        "bearerFormat": "API key",
    }
    assert schema["paths"]["/v1/protected"]["get"]["security"] == [{"BearerAuth": []}]
