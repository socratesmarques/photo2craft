from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    data_dir: Path = ROOT / "data"
    database_url: str = ""
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, le=8 * 1024 * 1024)
    max_request_bytes: int = Field(default=8 * 1024 * 1024, ge=2048, le=16 * 1024 * 1024)
    max_image_pixels: int = Field(default=16_000_000, ge=1, le=32_000_000)
    max_blocks: int = Field(default=50_000, ge=1, le=100_000)
    max_dimension: int = Field(default=64, ge=9, le=128)
    max_projects: int = Field(default=200, ge=1, le=10000)
    ai_provider: Literal['gemini', 'ollama', 'disabled'] = 'gemini'
    generation_mode: Literal['architectural', 'legacy'] = 'architectural'
    gemini_api_key: SecretStr = SecretStr('')
    gemini_model: str = 'gemini-3.8-flash'
    gemini_free_tier_confirmed: bool = False
    fallback_provider: Literal['none', 'ollama'] = 'none'
    ai_max_attempts: int = Field(default=3, ge=1, le=3)
    ai_daily_call_limit: int = Field(default=20, ge=1, le=1000)
    enable_visual_refinement: bool = True
    max_refinement_passes: int = Field(default=2, ge=0, le=3)
    max_reference_images: int = Field(default=4, ge=1, le=4)
    enable_generation_cache: bool = True
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3-vl:8b"
    ai_timeout_seconds: int = Field(default=600, ge=10, le=900)
    ai_max_output_tokens: int = Field(default=16000, ge=1000, le=24000)
    ai_context_tokens: int = Field(default=16384, ge=8192, le=32768)

    visual_debug: bool = False
    depth_model_path: str = ""
    depth_timeout_seconds: int = Field(default=45, ge=1, le=120)

    @model_validator(mode='after')
    def validate_provider(self):
        # Explicit reviewed allowlist, never a paid model or moving "latest" alias.
        if self.ai_provider == 'gemini' and self.gemini_model not in {
            'gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.5-flash-lite'
        }:
            raise ValueError('GEMINI_MODEL sem nível gratuito verificado; consulte docs/gemini-free-tier.md')
        if self.ai_provider == 'gemini' and self.generation_mode != 'architectural':
            raise ValueError('Gemini exige GENERATION_MODE=architectural')
        if self.ai_provider == 'ollama' or self.fallback_provider == 'ollama':
            from urllib.parse import urlsplit
            url = urlsplit(self.ollama_url)
            if url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.query or url.fragment:
                raise ValueError('OLLAMA_URL inválida')
            if not self.ollama_model.strip():
                raise ValueError('OLLAMA_MODEL vazio')
        return self

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'photo2craft.db'}"
