"""Unit tests: app factory, request-id middleware, health without a DB."""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def test_health_without_database(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.get("/health")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "miithii-engine"
    assert body["database"] == "not-configured"
    assert response.headers["x-request-id"]  # middleware ran


def test_request_id_is_echoed(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.get("/health", headers={"x-request-id": "test-123"})
    finally:
        get_settings.cache_clear()

    assert response.headers["x-request-id"] == "test-123"
