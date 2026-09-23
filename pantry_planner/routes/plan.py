"""Weekly meal plan: a Monday-to-Sunday grid with breakfast, lunch and dinner."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .. import services
from ..deps import DB, CurrentUser, Today
from ..models import SLOT_ORDER, MealPlanEntry
from ..security import verify_csrf
from ..web import flash, is_htmx, redirect, render

router = APIRouter(prefix="/plan", dependencies=[Depends(verify_csrf)])

SLOTS = [s.value for s in SLOT_ORDER]


def _cell(request: Request, db: DB, user_id: int, day: dt.date, slot: str) -> Response:
    recipes = services.list_recipes(db, user_id)
    return render(
        request,
        "partials/plan_cell.html",
        {
            "day": day,
            "slot": slot,
            "entries": services.entries_for_cell(db, user_id, day, slot),
            "recipes": recipes,
        },
    )


@router.get("")
def plan_page(
    request: Request, db: DB, user: CurrentUser, today: Today, week: str | None = None
) -> Response:
    monday = services.parse_week(week, today)
    entries = services.week_entries(db, user.id, monday)
    return render(
        request,
        "plan.html",
        {
            "nav": "plan",
            "monday": monday,
            "sunday": monday + dt.timedelta(days=6),
            "prev_week": (monday - dt.timedelta(days=7)).isoformat(),
            "next_week": (monday + dt.timedelta(days=7)).isoformat(),
            "this_week": services.week_start(today) == monday,
            "grid": services.plan_grid(entries, monday),
            "slots": SLOTS,
            "recipes": services.list_recipes(db, user.id),
            "today": today,
            "planned": len(entries),
        },
    )


@router.post("")
def add_entry(
    request: Request,
    db: DB,
    user: CurrentUser,
    day: Annotated[str, Form()],
    slot: Annotated[str, Form()],
    recipe_id: Annotated[int, Form()],
    servings: Annotated[str, Form()] = "",
) -> Response:
    try:
        when = dt.date.fromisoformat(day)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid day") from None
    if slot not in SLOTS:
        raise HTTPException(status_code=400, detail="Invalid meal slot")
    recipe = services.get_recipe(db, user.id, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    try:
        n = int(servings) if servings.strip() else recipe.servings
    except ValueError:
        n = recipe.servings
    n = max(1, min(n, 50))

    existing = db.scalar(
        select(MealPlanEntry).where(
            MealPlanEntry.user_id == user.id,
            MealPlanEntry.day == when,
            MealPlanEntry.slot == slot,
            MealPlanEntry.recipe_id == recipe.id,
        )
    )
    if existing is not None:
        existing.servings = n
    else:
        db.add(
            MealPlanEntry(user_id=user.id, day=when, slot=slot, recipe_id=recipe.id, servings=n)
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()

    if is_htmx(request):
        return _cell(request, db, user.id, when, slot)
    flash(request, f"Planned {recipe.title} for {when:%A} {slot}.")
    return redirect(f"/plan?week={services.week_start(when).isoformat()}")


@router.post("/{entry_id}/delete")
def delete_entry(request: Request, entry_id: int, db: DB, user: CurrentUser) -> Response:
    entry = db.scalar(
        select(MealPlanEntry).where(MealPlanEntry.id == entry_id, MealPlanEntry.user_id == user.id)
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Plan entry not found")
    day, slot = entry.day, entry.slot
    db.delete(entry)
    db.commit()
    if is_htmx(request):
        return _cell(request, db, user.id, day, slot)
    return redirect(f"/plan?week={services.week_start(day).isoformat()}")
