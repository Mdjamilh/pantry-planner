"""Application settings, read from environment variables (and an optional .env file)."""

from __future__ import annotations

import secrets
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEMO_DB_URL = "sqlite:////tmp/pantry-planner-demo.db"
LOCAL_DB_URL = "sqlite:///./pantry-planner.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database. When unset we pick a SQLite file: a local one for development,
    # or a throwaway one in /tmp when running on Vercel (demo mode).
    database_url: str = ""

    # Signs the session cookie. Generated per process when unset, which is fine
    # locally but logs everyone out on restart, so set it in production.
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))

    # Claude. Without a key the app answers with the rule-based fallback.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-5-5"
    ai_timeout_seconds: float = 20.0

    # Demo mode seeds a demo account and shows the "demo resets" banner.
    # Defaults to on when running on Vercel without a real database.
    demo_mode: bool | None = None
    demo_reset_hours: float = 6.0

    # Vercel sets VERCEL=1 in every deployment.
    vercel: str = ""

    # Run Alembic migrations on startup. Handy for SQLite and the demo.
    auto_migrate: bool = True

    # Mark cookies Secure. On by default on Vercel.
    secure_cookies: bool | None = None

    expiring_soon_days: int = 3

    @model_validator(mode="after")
    def _derive_defaults(self) -> Settings:
        on_vercel = bool(self.vercel)
        if not self.database_url:
            self.database_url = DEMO_DB_URL if on_vercel else LOCAL_DB_URL
            if self.demo_mode is None:
                self.demo_mode = on_vercel
        if self.demo_mode is None:
            self.demo_mode = False
        if self.secure_cookies is None:
            self.secure_cookies = on_vercel
        # Heroku-style URLs use postgres://; SQLAlchemy wants an explicit driver.
        if self.database_url.startswith("postgres://"):
            self.database_url = "postgresql+psycopg://" + self.database_url[len("postgres://") :]
        elif self.database_url.startswith("postgresql://"):
            self.database_url = (
                "postgresql+psycopg://" + self.database_url[len("postgresql://") :]
            )
        return self

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key.strip())

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
