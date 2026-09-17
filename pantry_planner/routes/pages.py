"""Dashboard ("Today")."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from .. import services
from ..deps import DB, AppSettings, CurrentUser, Today
from ..models import SLOT_ORDER
from ..security import verify_csrf
from ..web import render

router = APIRouter(dependencies=[Depends(verify_csrf)])


@router.get("/")
def dashboard(
    request: Request, db: DB, user: CurrentUser, today: Today, settings: AppSettings
) -> Response:
    items = services.list_pantry(db, user.id)
    monday = services.week_start(today)
    entries = services.week_entries(db, user.id, monday)
    todays = [e for e in entries if e.day == today]
    todays.sort(key=lambda e: [s.value for s in SLOT_ORDER].index(e.slot))
    shopping = services.shopping_for_week(db, user.id, monday, today)
    return render(
        request,
        "dashboard.html",
        {
            "nav": "today",
            "today": today,
            "expiring": services.expiring(items, today, settings.expiring_soon_days),
            "pantry_count": len(items),
            "recipe_count": len(services.list_recipes(db, user.id)),
            "week_count": len(entries),
            "todays": todays,
            "shopping_count": len(shopping),
            "soon_days": settings.expiring_soon_days,
        },
    )
