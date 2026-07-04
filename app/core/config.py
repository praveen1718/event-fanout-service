from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """12-factor configuration; every value overridable via environment variable."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/events.db"
    log_level: str = "INFO"

    # Delivery worker (used from iteration 2 onward; defined now so the
    # contract is stable).
    webhook_timeout_s: float = 10.0
    max_delivery_attempts: int = 5
    backoff_base_s: float = 2.0
    worker_poll_interval_s: float = 1.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
