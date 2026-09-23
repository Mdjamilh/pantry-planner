"""'What can I cook?': suggestions from Claude or the local matcher."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from .. import services
from ..deps import AI, DB, AppSettings, CurrentUser, Today
from ..security import verify_csrf
from ..web import is_htmx, render

router = APIRouter(prefix="/cook", dependencies=[Depends(verify_csrf)])


@router.get("")
def cook_page(
    request: Request, db: DB, user: CurrentUser, today: Today, settings: AppSettings
) -> Response:
    items = services.list_pantry(db, user.id)
    return render(
        request,
        "cook.html",
        {
            "nav": "cook",
            "expiring": services.expiring(items, today, settings.expiring_soon_days),
            "pantry_count": len(items),
            "today": today,
        },
    )


@router.post("/suggest")
def suggest(
    request: Request,
    db: DB,
    user: CurrentUser,
    today: Today,
    assistant: AI,
    settings: AppSettings,
) -> Response:
    items = services.list_pantry(db, user.id)
    limiter = request.app.state.ai_limiter
    limited = settings.ai_enabled and not limiter.allow(f"suggest:{user.id}")
    if limited:
        result = None
    else:
        facts = services.pantry_facts(items, today)
        book = services.recipe_candidates(services.list_recipes(db, user.id))
        result = assistant.suggest(facts, book)
    ctx = {
        "nav": "cook",
        "result": result,
        "limited": limited,
        "pantry_count": len(items),
        "expiring": services.expiring(items, today, settings.expiring_soon_days),
        "today": today,
    }
    if is_htmx(request):
        return render(request, "partials/suggestions.html", ctx)
    return render(request, "cook.html", ctx)
