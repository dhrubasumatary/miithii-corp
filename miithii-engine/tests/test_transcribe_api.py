"""Unit tests: POST /v1/transcribe (dictation).

No DB and no network: auth is overridden (the real chain's no-credentials
path gets its own test via a stubbed session), and the outbound Sarvam call
runs against httpx.MockTransport through the same client seam production
uses. The live-key path was exercised by hand against the real provider.
"""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.routes.transcribe import _sarvam_transcribe
from app.security import Principal, require_principal

FAKE_KEY = "sk_test_fake"


class _FakeTenant:
    id = "00000000-0000-0000-0000-000000000000"


def _principal() -> Principal:
    return Principal(_FakeTenant(), None)  # type: ignore[arg-type]


async def _stub_session():
    yield None


def _client(override_auth: bool = True) -> TestClient:
    app = create_app()
    if override_auth:
        app.dependency_overrides[require_principal] = _principal
    else:
        # the auth chain's first dependency is the DB session; stub it so the
        # no-credentials 401 is testable without a database behind the app
        from app.db import get_session

        app.dependency_overrides[get_session] = _stub_session
    return TestClient(app)


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("SARVAM_API_KEY", FAKE_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _mock_sarvam(monkeypatch, handler) -> None:
    """Route the module's outbound client factory through MockTransport —
    the real request-building and error-mapping code runs, only the wire is
    faked."""

    def factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler), timeout=httpx.Timeout(30.0)
        )

    monkeypatch.setattr(
        "app.routes.transcribe._stt_client", factory, raising=True
    )


def test_transcribe_requires_auth():
    client = _client(override_auth=False)
    with client:
        response = client.post("/v1/transcribe", content=b"audio-bytes")
    assert response.status_code == 401


def test_transcribe_unconfigured(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    client = _client()
    with client:
        response = client.post("/v1/transcribe", content=b"audio-bytes")
    assert response.status_code == 503
    assert "isn't configured" in response.json()["detail"]


def test_transcribe_happy_path(monkeypatch):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content
        seen["auth"] = request.headers.get("api-subscription-key")
        seen["model_field"] = b'name="model"' in body
        seen["filename"] = b"dictation.webm" in body
        seen["clip"] = b"audio-bytes" in body
        return httpx.Response(
            200,
            json={
                "request_id": "req_1",
                "transcript": "  What is the refund policy?  ",
                "language_code": "en-IN",
            },
        )

    _mock_sarvam(monkeypatch, handler)
    client = _client()
    with client:
        response = client.post(
            "/v1/transcribe",
            content=b"audio-bytes",
            headers={"Content-Type": "audio/webm;codecs=opus"},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["text"] == "What is the refund policy?"  # trimmed, never padded
    assert body["language_code"] == "en-IN"
    assert seen["auth"] == FAKE_KEY
    assert seen["model_field"] and seen["filename"] and seen["clip"]


def test_transcribe_empty_body():
    client = _client()
    with client:
        response = client.post(
            "/v1/transcribe", content=b"", headers={"Content-Type": "audio/webm"}
        )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"]


@pytest.mark.parametrize(
    "upstream_status, expected_status, message_fragment",
    [
        (429, 429, "busy right now"),
        (401, 502, "isn't authorized"),
        (403, 502, "isn't authorized"),
        (413, 502, "too long"),
        (500, 502, "couldn't transcribe"),
    ],
)
def test_transcribe_provider_error_mapping(
    monkeypatch, upstream_status, expected_status, message_fragment
):
    _mock_sarvam(
        monkeypatch,
        lambda request: httpx.Response(upstream_status, text="provider detail"),
    )
    client = _client()
    with client:
        response = client.post(
            "/v1/transcribe",
            content=b"audio-bytes",
            headers={"Content-Type": "audio/webm"},
        )
    assert response.status_code == expected_status, response.text
    assert message_fragment in response.json()["detail"]


def test_transcribe_network_failure(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    _mock_sarvam(monkeypatch, handler)
    client = _client()
    with client:
        response = client.post(
            "/v1/transcribe",
            content=b"audio-bytes",
            headers={"Content-Type": "audio/webm"},
        )
    assert response.status_code == 502
    assert "couldn't reach" in response.json()["detail"]


def test_clip_filename_maps_containers():
    from app.routes.transcribe import _clip_filename

    assert _clip_filename("audio/webm;codecs=opus") == "dictation.webm"
    assert _clip_filename("audio/mp4") == "dictation.mp4"
    assert _clip_filename("audio/x-wav") == "dictation.wav"
    assert _clip_filename("video/whatever") == "dictation.webm"


def test_sarvam_transcribe_parses_fallback_shape(monkeypatch):
    """The provider has used both `transcript` and `text` historically."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"text": "fallback shape"})

    _mock_sarvam(monkeypatch, handler)
    result = asyncio.run(_sarvam_transcribe(b"x", "audio/wav", FAKE_KEY))
    assert result["text"] == "fallback shape"
