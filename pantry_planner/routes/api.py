"""Small JSON API (session-authenticated) plus a health check."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from .. import __version__, services
from ..deps import DB, AppSettings, CurrentUser, Today
from ..security import verify_csrf

router = APIRouter(dependencies=[Depends(verify_csrf)])


@router.get("/healthz")
def health(db: DB, settings: AppSettings) -> dict[str, Any]:
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "version": __version__,
        "database": "sqlite" if settings.is_sqlite else "postgresql",
        "ai": "claude" if settings.ai_enabled else "fallback",
        "demo": bool(settings.demo_mode),
    }


@router.get("/api/pantry")
def api_pantry(db: DB, user: CurrentUser, today: Today) -> dict[str, Any]:
    return {
        "items": [
            {
                "id": i.id,
                "name": i.name,
                "quantity": i.quantity,
                "unit": i.unit,
                "expires_on": i.expires_on.isoformat() if i.expires_on else None,
                "days_left": i.days_left(today),
            }
            for i in services.list_pantry(db, user.id)
        ]
    }


@router.get("/api/shopping-list")
def api_shopping(
    db: DB, user: CurrentUser, today: Today, week: str | None = None
) -> dict[str, Any]:
    monday = services.parse_week(week, today)
    items = services.shopping_for_week(db, user.id, monday, today)
    return {
        "week_start": monday.isoformat(),
        "items": [
            {
                "name": i.name,
                "quantity": i.quantity,
                "unit": i.unit,
                "recipes": i.recipes,
                "note": i.note,
            }
            for i in items
        ],
    }
