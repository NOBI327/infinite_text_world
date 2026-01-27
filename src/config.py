"""Application configuration loaded from environment variables and .env file."""

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
    GEMINI_API_KEY: str = ""
    SYNC_TIMEZONE: str = "Asia/Tokyo"


settings = Settings()
