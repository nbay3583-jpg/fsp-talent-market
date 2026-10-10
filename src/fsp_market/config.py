from functools import lru_cache
from typing import Final

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://fsp:change-me@localhost:5432/fsp_market"
    jwt_secret: str = "dev-only-secret"
    environment: str = "local"
    app_name: str = "FSP Talent Market"
    demo_mode: bool = (
        False  # enables demo-login and reference-answer helper; never enable in production
    )
    validation_artifact: str = "artifacts/validation/latest.json"
    # Email (verification links). Without SMTP_HOST the message is only logged / kept in the
    # in-process outbox (local development and tests); nothing is ever sent.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "no-reply@fsp-talent-market.local"
    smtp_starttls: bool = True
    public_base_url: str = "http://localhost:8000"
    email_token_ttl_hours: int = 24


@lru_cache
def get_settings() -> Settings:
    return Settings()


__all__: Final = ["Settings", "get_settings"]
