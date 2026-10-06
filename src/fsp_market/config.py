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


@lru_cache
def get_settings() -> Settings:
    return Settings()


__all__: Final = ["Settings", "get_settings"]
