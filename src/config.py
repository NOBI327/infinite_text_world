"""Application configuration loaded from environment variables and .env file."""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Values are loaded from environment variables first,
    then from a .env file in the project root as fallback.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    DATABASE_URL: str = "sqlite:///./dev.db"
    DEBUG: bool = True
    SYNC_TIMEZONE: str = "Asia/Tokyo"
    LOG_LEVEL: str = "INFO"

    # AI Provider settings
    AI_PROVIDER: str = "mock"
    AI_API_KEY: Optional[str] = None
    AI_MODEL: Optional[str] = None
    AI_BASE_URL: Optional[str] = None


settings = Settings()
