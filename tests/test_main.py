import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from fsp_market import __version__
from fsp_market.main import HealthResponse, app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "FSP Talent Market"
    assert body["version"] == __version__


def test_openapi_document_contains_health_path() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths


def test_app_title_is_fsp_talent_market() -> None:
    assert app.title == "FSP Talent Market"


def test_health_response_rejects_missing_field() -> None:
    with pytest.raises(ValidationError):
        HealthResponse(status="ok")
