from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration for PP-DocLayout.

    Values can be set via:
    1. Environment variables (prefix: PPDOCLAYOUT_)
    2. .env file
    3. Default values
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="PPDOCLAYOUT_",
    )

    # ===== vLLM/Gemma Server Settings =====
    vllm_base_url: str = Field(
        default="http://127.0.0.1:8001/v1",
        description="Base URL for vLLM server"
    )
    vllm_context_window: int = Field(
        default=4096,
        description="Total prompt and output token limit configured on vLLM",
    )
    translation_max_input_tokens: int = Field(
        default=2048,
        description="TranslateGemma publisher-declared maximum input context",
    )
    vllm_chat_template_reserve: int = Field(
        default=256,
        description="Conservative token reserve for the chat template",
    )
    vllm_retry_attempts: int = Field(
        default=2,
        description="Number of retry attempts for failed translation requests"
    )
    vllm_model_name: str = Field(
        default="Infomaniak-AI/vllm-translategemma-4b-it",
        description="Model name for vLLM"
    )

    # ===== PaddleOCR-VL Server Settings =====
    paddle_ocr_server_url: str = Field(
        default="http://127.0.0.1:8000/v1",
        description="URL for PaddleOCR-VL server"
    )
    paddle_ocr_backend: str = Field(
        default="vllm-server",
        description="Backend for PaddleOCR-VL (vllm-server or local)"
    )
    paddle_ocr_client_device: str = Field(
        default="auto",
        description=(
            "Device for local PaddleOCR document layout analysis models. "
            "Use 'auto', 'cpu', or 'gpu:0'."
        )
    )
    paddle_ocr_format_block_content: bool = Field(
        default=True,
        description="Format block content (LaTeX, math, table)"
    )
    paddle_ocr_use_doc_unwarping: bool = Field(
        default=False,
        description="Use document unwarping (deskew, straighten)"
    )
    paddle_ocr_use_chart_recognition: bool = Field(
        default=False,
        description="Parse charts separately"
    )
    paddle_ocr_merge_layout_blocks: bool = Field(
        default=True,
        description="Merge related layout blocks"
    )
    paddle_ocr_layout_detection_model_name: str = Field(
        default="PP-DocLayoutV3",
        description="Layout detection model name"
    )
    paddle_ocr_use_layout_detection: bool = Field(
        default=True,
        description="Use layout detection"
    )
    paddle_use_ocr_for_image_block: bool = Field(
        default=True,
        description="OCR for images"
    )

    # ===== Concurrent Request Settings =====
    max_concurrent_requests: int = Field(
        default=32,
        description="Max concurrent translation requests"
    )

    # ===== Path Settings =====
    output_dir: str = Field(
        default="output",
        description="Base output directory"
    )   

    playwright_browser_channel: str | None = Field(
        default=None,
        description=(
            "Playwright browser channel, for example 'chrome'. "
            "Leave unset to use Playwright-managed Chromium."
        ),
    )


settings = Settings()
