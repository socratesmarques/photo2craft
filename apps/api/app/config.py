from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    data_dir: Path = ROOT / "data"
    database_url: str = ""
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, le=8 * 1024 * 1024)
    max_request_bytes: int = Field(default=8 * 1024 * 1024, ge=2048, le=16 * 1024 * 1024)
    max_image_pixels: int = Field(default=16_000_000, ge=1, le=32_000_000)
    max_blocks: int = Field(default=50_000, ge=1, le=100_000)
    max_dimension: int = Field(default=64, ge=9, le=128)
    max_projects: int = Field(default=200, ge=1, le=10000)
    ai_provider: str = "ollama"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma4:e2b"
    ai_timeout_seconds: int = Field(default=600, ge=10, le=900)
    ai_max_output_tokens: int = Field(default=16000, ge=1000, le=24000)
    ai_context_tokens: int = Field(default=16384, ge=8192, le=32768)

    visual_debug: bool = False
    depth_model_path: str = ""
    depth_timeout_seconds: int = Field(default=45, ge=1, le=120)

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'photo2craft.db'}"
