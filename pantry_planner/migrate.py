"""Run Alembic migrations from code (used on startup and in tests)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

PACKAGE_DIR = Path(__file__).resolve().parent


def alembic_config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(PACKAGE_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def upgrade_to_head(engine: Engine) -> None:
    cfg = alembic_config(str(engine.url.render_as_string(hide_password=False)))
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
