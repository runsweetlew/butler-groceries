"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://butlergroceries:butlergroceries_dev@localhost:5433/butlergroceries"
    database_url_sync: str = "postgresql://butlergroceries:butlergroceries_dev@localhost:5433/butlergroceries"

    # Anthropic
    anthropic_api_key: str = ""

    # Home Assistant Calendar Integration
    ha_url: str = ""  # e.g. https://6g4hp0yxylk47d9p85gxoala2lvs1w8l.ui.nabu.casa
    ha_token: str = ""  # Long-lived access token
    ha_calendars: str = "calendar.runsweetlew_gmail_com"  # Comma-separated entity IDs

    # Logging
    log_level: str = "INFO"

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Meijer API (python_Meijer library)
    meijer_auth_token: str = ""  # Bearer token captured via mitmproxy
    meijer_refresh_token: str = ""  # Refresh token
    meijer_store_id: str = "217"  # Default Meijer store ID

    # Images
    image_dir: str = "./data/images"

    # App
    app_name: str = "Butler Groceries"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
