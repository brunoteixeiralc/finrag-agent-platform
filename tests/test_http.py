"""Tests for request identifiers, public errors, and closed CORS defaults."""

from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

from app.http import REQUEST_ID_HEADER, RequestIdMiddleware, register_error_handlers
from app.main import create_app
from app.settings import Settings


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(environment="test", api_key="test-api-key", _env_file=None)
    with TestClient(create_app(settings=settings)) as test_client:
        yield test_client


def test_valid_client_request_id_is_preserved(client: TestClient) -> None:
    request_id = "4b987954-6230-4f67-9c10-ecce963ddba9"

    response = client.get("/health", headers={REQUEST_ID_HEADER: request_id})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == request_id


def test_invalid_client_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health", headers={REQUEST_ID_HEADER: "not-a-valid-uuid"})

    generated_request_id = response.headers[REQUEST_ID_HEADER]
    assert str(UUID(generated_request_id)) == generated_request_id
    assert generated_request_id != "not-a-valid-uuid"


def test_framework_errors_use_uniform_safe_envelope(client: TestClient) -> None:
    response = client.get("/route-that-does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "invalid_request",
            "message": "The request could not be completed.",
        },
        "request_id": response.headers[REQUEST_ID_HEADER],
    }


def test_public_infrastructure_and_documentation_require_no_authentication(
    client: TestClient,
) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_cors_is_denied_by_default(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 405
    assert "access-control-allow-origin" not in response.headers


def test_production_openapi_has_no_unused_security_scheme(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert "securitySchemes" not in schema.get("components", {})


def test_validation_errors_do_not_echo_rejected_input() -> None:
    application = FastAPI()
    application.add_middleware(RequestIdMiddleware)
    register_error_handlers(application)

    @application.get("/validation")
    async def validation_route(value: int = Query()) -> dict[str, int]:
        return {"value": value}

    secret_input = "invalid-value-containing-a-secret"
    with TestClient(application) as client:
        response = client.get("/validation", params={"value": secret_input})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert secret_input not in response.text


def test_unexpected_errors_hide_internal_details() -> None:
    application = FastAPI()
    application.add_middleware(RequestIdMiddleware)
    register_error_handlers(application)

    @application.get("/failure")
    async def failure_route() -> None:
        raise RuntimeError("private database host and SQL details")

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get("/failure")

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "internal_error",
        "message": "An unexpected error occurred.",
    }
    assert "private database" not in response.text
    assert response.json()["request_id"] == response.headers[REQUEST_ID_HEADER]
