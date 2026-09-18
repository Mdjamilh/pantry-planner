"""Pantry inventory: list, add, edit inline, delete."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from .. import services
from ..deps import DB, AppSettings, CurrentUser, Today
from ..models import PantryItem
from ..security import verify_csrf
from ..web import flash, is_htmx, redirect, render
from .forms import validate_pantry

router = APIRouter(prefix="/pantry", dependencies=[Depends(verify_csrf)])

COMMON_UNITS = ["", "g", "kg", "ml", "l", "tsp", "tbsp", "cup", "clove", "can", "head", "pack"]


def _page_context(db: DB, user_id: int, today: Today, settings: AppSettings) -> dict[str, object]:
    items = services.list_pantry(db, user_id)
    soon = settings.expiring_soon_days
    lefts = [i.days_left(today) for i in items]
    return {
        "nav": "pantry",
        "items": items,
        "today": today,
        "units": COMMON_UNITS,
        "soon_days": soon,
        "expired_count": sum(1 for d in lefts if d is not None and d < 0),
        "soon_count": sum(1 for d in lefts if d is not None and 0 <= d <= soon),
    }


def _own_item(db: DB, user_id: int, item_id: int) -> PantryItem:
    item = services.get_pantry_item(db, user_id, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Pantry item not found")
    return item


@router.get("")
def pantry_page(
    request: Request, db: DB, user: CurrentUser, today: Today, settings: AppSettings
) -> Response:
    return render(request, "pantry.html", _page_context(db, user.id, today, settings))


@router.post("")
def add_item(
    request: Request,
    db: DB,
    user: CurrentUser,
    today: Today,
    settings: AppSettings,
    name: Annotated[str, Form()] = "",
    quantity: Annotated[str, Form()] = "",
    unit: Annotated[str, Form()] = "",
    expires_on: Annotated[str, Form()] = "",
) -> Response:
    data = validate_pantry(name, quantity, unit, expires_on)
    if data.ok:
        db.add(
            PantryItem(
                user_id=user.id,
                name=data.name,
                quantity=data.quantity,
                unit=data.unit,
                expires_on=data.expires_on,
            )
        )
        db.commit()
    ctx = _page_context(db, user.id, today, settings)
    if not data.ok:
        ctx.update(errors=data.errors, form=data.raw)
    if is_htmx(request):
        # htmx only swaps 2xx responses, so validation errors come back as 200.
        return render(request, "partials/pantry_panel.html", ctx)
    if not data.ok:
        return render(request, "pantry.html", ctx, status_code=400)
    flash(request, f"Added {data.name}.")
    return redirect("/pantry")


@router.get("/{item_id}/row")
def item_row(request: Request, item_id: int, db: DB, user: CurrentUser, today: Today) -> Response:
    item = _own_item(db, user.id, item_id)
    return render(request, "partials/pantry_row.html", {"item": item, "today": today})


@router.get("/{item_id}/edit")
def edit_row(request: Request, item_id: int, db: DB, user: CurrentUser, today: Today) -> Response:
    item = _own_item(db, user.id, item_id)
    return render(
        request,
        "partials/pantry_row_edit.html",
        {"item": item, "today": today, "units": COMMON_UNITS},
    )


@router.post("/{item_id}")
def update_item(
    request: Request,
    item_id: int,
    db: DB,
    user: CurrentUser,
    today: Today,
    name: Annotated[str, Form()] = "",
    quantity: Annotated[str, Form()] = "",
    unit: Annotated[str, Form()] = "",
    expires_on: Annotated[str, Form()] = "",
) -> Response:
    item = _own_item(db, user.id, item_id)
    data = validate_pantry(name, quantity, unit, expires_on)
    if not data.ok:
        return render(
            request,
            "partials/pantry_row_edit.html",
            {"item": item, "today": today, "units": COMMON_UNITS, "errors": data.errors},
        )
    item.name, item.quantity, item.unit, item.expires_on = (
        data.name,
        data.quantity,
        data.unit,
        data.expires_on,
    )
    db.commit()
    if is_htmx(request):
        return render(request, "partials/pantry_row.html", {"item": item, "today": today})
    return redirect("/pantry")


@router.post("/{item_id}/delete")
def delete_item(request: Request, item_id: int, db: DB, user: CurrentUser) -> Response:
    item = _own_item(db, user.id, item_id)
    name = item.name
    db.delete(item)
    db.commit()
    if is_htmx(request):
        return HTMLResponse("")
    flash(request, f"Removed {name}.")
    return redirect("/pantry")
