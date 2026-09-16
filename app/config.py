"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: Literal["dev", "test", "prod"] = "dev"
    secret_key: str = "dev-secret-change-me"

    # DB
    database_url: str = "sqlite+aiosqlite:///./ledgerflow.db"

    # Storage
    upload_dir: Path = _PROJECT_ROOT / "data/uploads"

    # AI
    ai_provider: Literal["mock", "openai"] = "mock"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Mail
    mail_provider: Literal["mock", "gmail"] = "mock"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""
    gmail_lookback_days: int = Field(default=30, ge=1, le=365)
    mail_poll_interval_seconds: int = 60
    mail_webhook_secret: str = ""

    # OCR
    ocr_provider: Literal["mock", "tesseract", "mistral"] = "mock"
    mistral_api_key: str = ""
    mistral_ocr_endpoint: str = "https://api.mistral.ai/v1/ocr"

    # Business rules
    required_docs_company: str = "invoice,bank_statement"
    required_docs_sole_prop: str = "invoice,bank_statement,receipt"

    @property
    def required_docs_by_kind(self) -> dict[str, list[str]]:
        return {
            "company": [s.strip() for s in self.required_docs_company.split(",") if s.strip()],
            "sole_prop": [s.strip() for s in self.required_docs_sole_prop.split(",") if s.strip()],
        }


def _project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else _PROJECT_ROOT / path


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.upload_dir = _project_path(s.upload_dir).resolve()
    sqlite_prefix = "sqlite+aiosqlite:///"
    if s.database_url.startswith(sqlite_prefix):
        database_path = s.database_url.removeprefix(sqlite_prefix)
        if database_path not in {":memory:", ""}:
            resolved = _project_path(database_path).resolve()
            s.database_url = f"{sqlite_prefix}{resolved.as_posix()}"
    s.upload_dir.mkdir(parents=True, exist_ok=True)
    return s


settings = get_settings()