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
    voicestudio_url: str = "http://127.0.0.1:3900"  # VoiceStudio (voz local); ATLAS_VOICESTUDIO_URL
    voicestudio_api_key: str | None = None  # solo si VoiceStudio está en otro equipo (OMNIVOICE_API_KEY)
    sync_interval_s: int = 1800
    frontend_dist: Path = ATLAS_ROOT / "frontend" / "dist"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Cabecera Host aceptada (protege contra DNS rebinding: una web maliciosa no puede hablar con tu VISTAN local).
    # *.ts.net = Tailscale Serve (móvil). Si escuchas fuera de 127.0.0.1 (ATLAS_HOST), añade aquí tu nombre o IP.
    allowed_hosts: list[str] = ["127.0.0.1", "localhost", "[::1]", "*.ts.net", "testserver"]

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
