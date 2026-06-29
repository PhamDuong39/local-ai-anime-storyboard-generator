from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


OutputPresetId = Literal[
    "youtube_standard",
    "youtube_high",
    "low_vram_preview",
    "low_vram_tiny",
    "square_preview",
    "vertical_short",
]
FaceIdMode = Literal["auto", "force", "disabled"]


class Settings(BaseSettings):
    """Application configuration loaded from the environment and local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openai_api_key: SecretStr | None = None
    openai_scene_model: str = "gpt-5.4-mini"
    openai_prompt_model: str = "gpt-5.4-mini"
    # TODO(M8): Set OPENAI_MOCK_MODE=false after a valid OpenAI API key is
    # configured and real scene/prompt calls are verified.
    openai_mock_mode: bool = True
    openai_context_token_limit: int = 128000
    openai_request_overhead_tokens: int = 4000
    projects_root: Path = Path("./projects")
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    image_model_id: str = "stabilityai/stable-diffusion-xl-base-1.0"
    low_vram_image_model_id: str = "stable-diffusion-v1-5/stable-diffusion-v1-5"
    default_output_preset: OutputPresetId = "youtube_standard"
    enable_ip_adapter_faceid: FaceIdMode = "auto"
    force_low_vram_mode: bool = False
    log_level: str = "INFO"

    @property
    def has_openai_api_key(self) -> bool:
        return bool(
            self.openai_api_key and self.openai_api_key.get_secret_value().strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
