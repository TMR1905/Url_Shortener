from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    application settings will be in here
    """

    #Application settings
    APP_NAME: str = "Fastapi URL Shortener"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"


    #DATABASE CONFIG
    DATABASE_URL: str
    DB_ECHO: bool = False

    # URL Shortener Config
    HASHIDS_SALT: str = "your-secret-salt-change-in-production"
    HASHIDS_MIN_LENGTH: int = 6
    BASE_URL: str = "http://localhost:8000"


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

@lru_cache()
def get_settings() -> Settings:
    """
    Create and cache settings instance
    """
    return Settings()

settings = get_settings()