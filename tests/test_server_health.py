"""Tests for OpenAI-compatible server health checks."""

from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from pp_doclayout.utils import server_health


def test_check_server_health_returns_available_for_valid_response(monkeypatch):
    """A valid /v1/models response marks the server as available."""

    def fake_urlopen(request, timeout):
        assert request.full_url == "http://127.0.0.1:8001/v1/models"
        assert request.get_header("Accept") == "application/json"
        assert timeout == 3.5
        return BytesIO(b'{"object": "list", "data": []}')

    monkeypatch.setattr(server_health, "urlopen", fake_urlopen)

    result = server_health.check_server_health(
        name="TranslateGemma",
        base_url="http://127.0.0.1:8001/v1/",
        timeout=3.5,
    )

    assert result == server_health.ServerHealth(
        name="TranslateGemma",
        url="http://127.0.0.1:8001/v1/models",
        available=True,
        message="Server is ready",
    )


def test_check_server_health_handles_http_error(monkeypatch):
    """An HTTP failure is returned as an unavailable health result."""

    def fake_urlopen(request, timeout):
        raise HTTPError(
            url=request.full_url,
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(server_health, "urlopen", fake_urlopen)

    result = server_health.check_server_health(
        name="PaddleOCR-VL",
        base_url="http://127.0.0.1:8000/v1",
    )

    assert result.available is False
    assert result.message == "HTTP 503"


def test_check_server_health_handles_connection_error(monkeypatch):
    """A connection failure is returned instead of being raised."""

    def fake_urlopen(request, timeout):
        raise URLError("Connection refused")

    monkeypatch.setattr(server_health, "urlopen", fake_urlopen)

    result = server_health.check_server_health(
        name="TranslateGemma",
        base_url="http://127.0.0.1:8001/v1",
    )

    assert result.available is False
    assert "Connection refused" in result.message


def test_check_server_health_rejects_invalid_json(monkeypatch):
    """A non-JSON response does not count as a healthy server."""

    monkeypatch.setattr(
        server_health,
        "urlopen",
        lambda request, timeout: BytesIO(b"not JSON"),
    )

    result = server_health.check_server_health(
        name="TranslateGemma",
        base_url="http://127.0.0.1:8001/v1",
    )

    assert result.available is False
    assert result.message == "Server returned invalid JSON"


@pytest.mark.parametrize(
    "payload",
    [
        b"[]",
        b'{"data": {}}',
        b'{"object": "list"}',
    ],
)
def test_check_server_health_rejects_unexpected_payload(
    monkeypatch,
    payload,
):
    """The response must contain an OpenAI-compatible data list."""

    monkeypatch.setattr(
        server_health,
        "urlopen",
        lambda request, timeout: BytesIO(payload),
    )

    result = server_health.check_server_health(
        name="TranslateGemma",
        base_url="http://127.0.0.1:8001/v1",
    )

    assert result.available is False
    assert result.message == "Unexpected /v1/models response"
