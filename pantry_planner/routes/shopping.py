"""Shopping list for a week, with "bought it" moving items into the pantry."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response

from .. import services, units
from ..deps import DB, CurrentUser, Today
from ..models import PantryItem
from ..security import verify_csrf
from ..web import flash, is_htmx, redirect, render
from .forms import parse_quantity_field

router = APIRouter(prefix="/shopping", dependencies=[Depends(verify_csrf)])


def _context(db: DB, user_id: int, monday: dt.date, today: dt.date) -> dict[str, object]:
    items = services.shopping_for_week(db, user_id, monday, today)
    return {
        "nav": "shopping",
        "items": items,
        "monday": monday,
        "sunday": monday + dt.timedelta(days=6),
        "week": monday.isoformat(),
        "prev_week": (monday - dt.timedelta(days=7)).isoformat(),
        "next_week": (monday + dt.timedelta(days=7)).isoformat(),
        "planned": len(services.week_entries(db, user_id, monday)),
        "plain_text": "\n".join(
            f"- {i.name}" + (f": {i.amount_text}" if i.amount_text else "") for i in items
        ),
    }


@router.get("")
def shopping_page(
    request: Request, db: DB, user: CurrentUser, today: Today, week: str | None = None
) -> Response:
    monday = services.parse_week(week, today)
    return render(request, "shopping.html", _context(db, user.id, monday, today))


@router.post("/bought")
def mark_bought(
    request: Request,
    db: DB,
    user: CurrentUser,
    today: Today,
    name: Annotated[str, Form()],
    quantity: Annotated[str, Form()] = "",
    unit: Annotated[str, Form()] = "",
    week: Annotated[str, Form()] = "",
) -> Response:
    monday = services.parse_week(week, today)
    clean_name = " ".join(name.split())[:120]
    qty = parse_quantity_field(quantity) or 1.0
    if clean_name:
        db.add(
            PantryItem(
                user_id=user.id,
                name=clean_name,
                quantity=qty,
                unit=units.normalize_unit(unit)[:20],
            )
        )
        db.commit()
    if is_htmx(request):
        ctx = _context(db, user.id, monday, today)
        ctx["bought"] = clean_name
        return render(request, "partials/shopping_list.html", ctx)
    flash(request, f"Moved {clean_name} into the pantry.")
    return redirect(f"/shopping?week={monday.isoformat()}")
