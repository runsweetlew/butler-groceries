"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://dukecook:dukecook_dev@localhost:5433/dukecook"
    database_url_sync: str = "postgresql://dukecook:dukecook_dev@localhost:5433/dukecook"

    # Anthropic
    anthropic_api_key: str = ""

    # Home Assistant Calendar Integration
    ha_url: str = ""  # e.g. https://6g4hp0yxylk47d9p85gxoala2lvs1w8l.ui.nabu.casa
    ha_token: str = ""  # Long-lived access token
    ha_calendars: str = "calendar.trevor_duke_gmail_com,calendar.runsweetlew_gmail_com,calendar.the_house_calendar"  # Comma-separated entity IDs

    # Logging
    log_level: str = "INFO"

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Kroger API
    kroger_client_id: str = ""
    kroger_client_secret: str = ""
    kroger_store_id: str = "01800661"  # Kroger Middlebelt, Farmington Hills MI

    # Images
    image_dir: str = "./data/images"

    # App
    app_name: str = "DukeCook"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
