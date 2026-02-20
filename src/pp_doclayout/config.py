from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    engine: str = "gemma"

    vllm_base_url: str = "http://127.0.0.1:8001/v1"
    vllm_max_tokens: int = 16384
    vllm_model_name: str = "Infomaniak-AI/vllm-translategemma-4b-it"
    output_dir: str = "output"

    paddle_ocr_server_url: str = "http://127.0.0.1:8000/v1"
    paddle_ocr_backend: str = "vllm-server"


settings = Settings()
