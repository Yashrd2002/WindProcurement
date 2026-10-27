from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    app_name: str = "Wind Procurement Intelligence API"
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"
    cache_ttl_seconds: int = 3600
    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"

    # HTTP client resilience settings
    http_timeout_seconds: float = 15.0
    http_connect_timeout_seconds: float = 5.0
    http_max_retries: int = 3
    http_max_connections: int = 50
    http_max_keepalive: int = 20

    # Business domain defaults
    default_target_month: str = "2026-01"
    default_cutoff_time: str = "12:00"
    default_timezone: str = "Europe/London"
    offline_mode: bool = False

    # AI Copilot settings
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
