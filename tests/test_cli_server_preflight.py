"""Tests for CLI server preflight checks."""

from types import SimpleNamespace

import pytest
import typer

from pp_doclayout import cli


def test_require_server_allows_available_server(monkeypatch):
    """A healthy server should let the command continue."""

    calls = []

    def fake_check_server_health(name, base_url):
        calls.append((name, base_url))
        return SimpleNamespace(
            name=name,
            url=f"{base_url}/models",
            available=True,
            message="Server is ready",
        )

    monkeypatch.setattr(cli, "check_server_health", fake_check_server_health)

    cli._require_server("TranslateGemma", "http://127.0.0.1:8001/v1")

    assert calls == [("TranslateGemma", "http://127.0.0.1:8001/v1")]


def test_require_server_exits_with_clear_message(monkeypatch):
    """An unavailable server should stop early with an actionable message."""

    messages = []

    def fake_check_server_health(name, base_url):
        return SimpleNamespace(
            name=name,
            url=f"{base_url}/models",
            available=False,
            message="Connection refused",
        )

    def fake_echo(message, *args, **kwargs):
        messages.append((message, kwargs.get("err", False)))

    monkeypatch.setattr(cli, "check_server_health", fake_check_server_health)
    monkeypatch.setattr(cli.typer, "echo", fake_echo)

    with pytest.raises(typer.Exit) as exc_info:
        cli._require_server("PaddleOCR-VL", "http://127.0.0.1:8000/v1")

    assert exc_info.value.exit_code == 1
    assert messages == [
        (
            "PaddleOCR-VL server is not ready: "
            "http://127.0.0.1:8000/v1/models",
            True,
        ),
        ("  Reason: Connection refused", True),
    ]
