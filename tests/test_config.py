"""Tests for config.py."""

import os

from pp_doclayout.config import Settings


def test_default_settings():
    """Test default configuration values."""
    settings = Settings()
    assert settings.engine == "gemma"
    assert settings.vllm_base_url == "http://127.0.0.1:8001/v1"
    assert settings.vllm_max_tokens == 16384
    assert settings.paddle_ocr_server_url == "http://127.0.0.1:8000/v1"
    assert settings.output_dir == "output"
    assert settings.batch_size_small == 16
    assert settings.batch_size_medium == 8
    assert settings.batch_size_large == 4
    assert settings.export_formats == ["html", "pdf"]


def test_env_override():
    """Test environment variable override."""
    os.environ["PPDOCLAYOUT_VLLM_BASE_URL"] = "http://test:9999/v1"
    os.environ["PPDOCLAYOUT_BATCH_SIZE_SMALL"] = "32"
    os.environ["PPDOCLAYOUT_EXPORT_FORMATS_RAW"] = "html,markdown"

    settings = Settings()
    assert settings.vllm_base_url == "http://test:9999/v1"
    assert settings.batch_size_small == 32
    assert settings.export_formats == ["html", "markdown"]

    # Clean up
    del os.environ["PPDOCLAYOUT_VLLM_BASE_URL"]
    del os.environ["PPDOCLAYOUT_BATCH_SIZE_SMALL"]
    del os.environ["PPDOCLAYOUT_EXPORT_FORMATS_RAW"]


def test_export_formats_parsing():
    """Test export_formats parsing from string."""
    settings = Settings(export_formats_raw="html,pdf,markdown")
    assert settings.export_formats == ["html", "pdf", "markdown"]
