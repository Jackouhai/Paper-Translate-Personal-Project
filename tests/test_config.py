"""Tests for config.py."""

import os

from pp_doclayout.config import Settings


def test_default_settings():
    """Test default configuration values."""
    settings = Settings(_env_file=None)
    assert settings.engine == "gemma"
    assert settings.vllm_base_url == "http://127.0.0.1:8001/v1"
    assert settings.vllm_max_tokens == 16384
    assert settings.paddle_ocr_server_url == "http://127.0.0.1:8000/v1"
    assert settings.paddle_ocr_client_device == "auto"
    assert settings.output_dir == "output"
    assert settings.export_formats == ["html", "pdf"]
    assert settings.playwright_browser_channel is None


def test_env_override():
    """Test environment variable override."""
    os.environ["PPDOCLAYOUT_VLLM_BASE_URL"] = "http://test:9999/v1"
    os.environ["PPDOCLAYOUT_EXPORT_FORMATS_RAW"] = "html,markdown"

    settings = Settings()
    assert settings.vllm_base_url == "http://test:9999/v1"
    assert settings.export_formats == ["html", "markdown"]

    # Clean up
    del os.environ["PPDOCLAYOUT_VLLM_BASE_URL"]
    del os.environ["PPDOCLAYOUT_EXPORT_FORMATS_RAW"]


def test_export_formats_parsing():
    """Test export_formats parsing from string."""
    settings = Settings(export_formats_raw="html,pdf,markdown")
    assert settings.export_formats == ["html", "pdf", "markdown"]


def test_playwright_browser_channel_env(monkeypatch):
    """Test selecting a system browser through an environment variable."""
    monkeypatch.setenv(
        "PPDOCLAYOUT_PLAYWRIGHT_BROWSER_CHANNEL",
        "chrome",
    )

    settings = Settings(_env_file=None)

    assert settings.playwright_browser_channel == "chrome"


def test_paddle_ocr_client_device_env(monkeypatch):
    """Test selecting a PaddleOCR helper model device through env."""
    monkeypatch.setenv("PPDOCLAYOUT_PADDLE_OCR_CLIENT_DEVICE", "gpu:0")

    settings = Settings(_env_file=None)

    assert settings.paddle_ocr_client_device == "gpu:0"
