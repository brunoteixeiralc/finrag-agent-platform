"""Tests for typed settings and secret handling."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.settings import Environment, Settings


@pytest.fixture(autouse=True)
def clear_finrag_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests independent from FINRAG_* variables on the host machine."""

    for variable_name in (
        "FINRAG_API_KEY",
        "FINRAG_APP_NAME",
        "FINRAG_DATABASE_URL",
        "FINRAG_ENVIRONMENT",
    ):
        monkeypatch.delenv(variable_name, raising=False)


def test_development_defaults_require_no_secrets() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment is Environment.DEVELOPMENT
    assert settings.database_url is None
    assert settings.api_key is None

    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_load_prefixed_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINRAG_ENVIRONMENT", "test")
    monkeypatch.setenv("FINRAG_APP_NAME", "FinRAG Test")
    monkeypatch.setenv("FINRAG_API_KEY", "local-test-api-key")

    settings = Settings(_env_file=None)

    assert settings.environment is Environment.TEST
    assert settings.app_name == "FinRAG Test"
    assert settings.api_key is not None
    assert settings.api_key.get_secret_value() == "local-test-api-key"


def test_production_requires_api_key_and_database_url() -> None:
    with pytest.raises(ValidationError) as captured_error:
        Settings(environment=Environment.PRODUCTION, _env_file=None)

    error_message = str(captured_error.value)
    assert "api_key" in error_message
    assert "database_url" in error_message


def test_secret_values_are_hidden_from_representations() -> None:
    api_key = "do-not-print-this-api-key"
    database_url = "postgresql://finrag:do-not-print-this-password@localhost/finrag"

    settings = Settings(api_key=api_key, database_url=database_url, _env_file=None)

    assert api_key not in repr(settings)
    assert database_url not in repr(settings)
    assert api_key not in settings.model_dump_json()
    assert database_url not in settings.model_dump_json()


def test_validation_errors_hide_invalid_input_values() -> None:
    secret_input = "invalid-environment-containing-a-secret"

    with pytest.raises(ValidationError) as captured_error:
        Settings(environment=secret_input, _env_file=None)

    assert secret_input not in str(captured_error.value)
