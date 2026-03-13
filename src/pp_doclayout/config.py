from functools import cached_property

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

    # ===== Engine Settings =====
    engine: str = "gemma"

    # ===== vLLM/Gemma Server Settings =====
    vllm_base_url: str = Field(
        default="http://127.0.0.1:8001/v1",
        description="Base URL for vLLM server"
    )
    vllm_max_tokens: int = Field(
        default=16384,
        description="Maximum tokens for generation"
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
    paddle_ocr_format_block_content: bool = Field(
        default=True,
        description="Format block content (LaTeX, math, table)"
    )
    paddle_ocr_use_doc_unwarping: bool = Field(
        default=True,
        description="Use document unwarping (deskew, straighten)"
    )
    paddle_ocr_use_chart_recognition: bool = Field(
        default=True,
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

    # ===== Batch Processing Settings =====
    batch_size_small: int = Field(
        default=16,
        description="Batch size for small texts (<100 tokens)"
    )
    batch_size_medium: int = Field(
        default=8,
        description="Batch size for medium texts (100-500 tokens)"
    )
    batch_size_large: int = Field(
        default=4,
        description="Batch size for large texts (>500 tokens)"
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

    # ===== Export Settings =====
    # Note: In .env file, use: PPDOCLAYOUT_EXPORT_FORMATS=html,pdf,markdown
    # The property export_formats returns a parsed list
    export_formats_raw: str = Field(
        default="html,pdf",
        description="Export formats (comma-separated: html,pdf,markdown)"
    )

    @cached_property
    def export_formats(self) -> list[str]:
        """Parse export_formats from comma-separated string.

        Returns:
            List of export formats
        """
        return [f.strip() for f in self.export_formats_raw.split(",")]


settings = Settings()
