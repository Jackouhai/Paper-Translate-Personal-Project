"""Tests for CLI PaddleOCR pipeline construction."""

import sys
from types import SimpleNamespace

from pp_doclayout import cli
from pp_doclayout.config import Settings


def test_create_paddle_ocr_pipeline_passes_resolved_device(monkeypatch):
    """The CLI should pass the resolved helper model device to PaddleOCRVL."""

    captured_kwargs = {}

    class FakePaddleOCRVL:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    monkeypatch.setitem(
        sys.modules,
        "paddleocr",
        SimpleNamespace(PaddleOCRVL=FakePaddleOCRVL),
    )
    monkeypatch.setattr(
        cli,
        "settings",
        Settings(_env_file=None, paddle_ocr_client_device="auto"),
    )
    monkeypatch.setattr(
        cli,
        "resolve_paddle_device",
        lambda configured_device: "gpu:0",
    )
    monkeypatch.setattr(cli.typer, "echo", lambda *args, **kwargs: None)

    pipeline = cli._create_paddle_ocr_pipeline()

    assert isinstance(pipeline, FakePaddleOCRVL)
    assert captured_kwargs["device"] == "gpu:0"
    assert captured_kwargs["vl_rec_backend"] == "vllm-server"
    assert captured_kwargs["vl_rec_server_url"] == "http://127.0.0.1:8000/v1"
