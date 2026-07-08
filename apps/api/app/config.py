from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./voxrelay.db"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    api_prefix: str = "/api/v1"
    demo_mode: bool = True
    cors_origins: str = "http://localhost:3000"
    access_token_minutes: int = 60
    refresh_token_days: int = 7
    rate_limit_per_minute: int = 180
    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


settings = Settings()
