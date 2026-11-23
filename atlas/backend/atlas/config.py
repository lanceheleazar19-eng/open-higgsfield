"""Configuración vía variables de entorno / backend/.env (claves nunca en código)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ATLAS_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ATLAS_", env_file=BACKEND_DIR / ".env", extra="ignore"
    )

    host: str = "127.0.0.1"  # solo local por defecto
    port: int = 8000
    data_dir: Path = ATLAS_ROOT / "data"
    database_url: str | None = None  # p.ej. postgresql+psycopg://... en el futuro
    timezone: str = "Europe/Madrid"
    ollama_url: str = "http://127.0.0.1:11434"
    frontend_dist: Path = ATLAS_ROOT / "frontend" / "dist"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def resolved_data_dir(self) -> Path:
        p = self.data_dir
        if not p.is_absolute():
            p = (BACKEND_DIR / p).resolve()
        return p

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.resolved_data_dir / 'atlas.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
