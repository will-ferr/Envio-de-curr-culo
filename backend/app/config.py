"""Configuração de infraestrutura lida do ambiente (.env).

Somente o que é necessário para o processo subir fica aqui. Tudo que o usuário
configura pela interface (chave de IA, Telegram, SMTP...) fica no banco,
criptografado — ver app/services/settings.py.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field("development", pattern="^(development|test|production)$")
    database_url: str = "postgresql+psycopg://candidaturas:candidaturas@localhost:5432/candidaturas"
    secret_key: str = Field(..., min_length=32, description="Assina sessões e deriva a chave de criptografia")
    data_dir: Path = Path("./data")
    public_url: str = "http://localhost:8000"
    cors_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "INFO"
    session_hours: int = 24 * 7
    worker_poll_seconds: float = 2.0
    sources_interval_minutes: int = 60

    @field_validator("secret_key")
    @classmethod
    def _not_placeholder(cls, v: str) -> str:
        if "troque" in v.lower() or "change-me" in v.lower():
            raise ValueError("SECRET_KEY ainda é o valor de exemplo; gere um com `openssl rand -hex 32`")
        return v

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
