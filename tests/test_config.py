"""Tests for config.py."""

from pp_doclayout.config import Settings


def test_default_settings():
    """Test default configuration values."""
    settings = Settings(_env_file=None)
    assert settings.vllm_base_url == "http://127.0.0.1:8001/v1"
    assert settings.vllm_context_window == 4096
    assert settings.translation_max_input_tokens == 2048
    assert settings.vllm_chat_template_reserve == 256
    assert settings.paddle_ocr_server_url == "http://127.0.0.1:8000/v1"
    assert settings.parse_api_base_url == "http://127.0.0.1:8082"
    assert settings.paddle_ocr_client_device == "auto"
    assert settings.output_dir == "output"
    assert settings.playwright_browser_channel is None


def test_env_override(monkeypatch):
    """Test environment variable override."""
    monkeypatch.setenv("PPDOCLAYOUT_VLLM_BASE_URL", "http://test:9999/v1")

    settings = Settings()
    assert settings.vllm_base_url == "http://test:9999/v1"


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
