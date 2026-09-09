"""Queries and helpers shared by the HTML routes and the JSON API.

Every query is scoped to one user; nothing here can read another account.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import units
from .ai.schemas import Candidate, PantryFact
from .models import SLOT_ORDER, MealPlanEntry, PantryItem, Recipe
from .shopping import Need, ShoppingItem, Stock, build_shopping_list, scale_quantity


def week_start(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def parse_week(value: str | None, today: dt.date) -> dt.date:
    if value:
        try:
            return week_start(dt.date.fromisoformat(value))
        except ValueError:
            pass
    return week_start(today)


def list_pantry(db: Session, user_id: int) -> list[PantryItem]:
    items = db.scalars(select(PantryItem).where(PantryItem.user_id == user_id)).all()
    # Soonest expiry first; items without a date go last, alphabetically.
    return sorted(items, key=lambda i: (i.expires_on is None, i.expires_on or dt.date.max, i.name.lower()))


def get_pantry_item(db: Session, user_id: int, item_id: int) -> PantryItem | None:
    return db.scalar(
        select(PantryItem).where(PantryItem.id == item_id, PantryItem.user_id == user_id)
    )


def expiring(items: list[PantryItem], today: dt.date, within_days: int) -> list[PantryItem]:
    out = []
    for item in items:
        left = item.days_left(today)
        if left is not None and left <= within_days:
            out.append(item)
    return out


def pantry_facts(items: list[PantryItem], today: dt.date) -> list[PantryFact]:
    return [PantryFact(name=i.name, days_left=i.days_left(today)) for i in items]


def list_recipes(db: Session, user_id: int, query: str = "") -> list[Recipe]:
    stmt = (
        select(Recipe)
        .where(Recipe.user_id == user_id)
        .options(selectinload(Recipe.ingredients))
        .order_by(Recipe.title)
    )
    if query.strip():
        stmt = stmt.where(Recipe.title.ilike(f"%{query.strip()}%"))
    return list(db.scalars(stmt).all())


def get_recipe(db: Session, user_id: int, recipe_id: int) -> Recipe | None:
    return db.scalar(
        select(Recipe)
        .where(Recipe.id == recipe_id, Recipe.user_id == user_id)
        .options(selectinload(Recipe.ingredients))
    )


def recipe_candidates(recipes: list[Recipe]) -> list[Candidate]:
    return [
        Candidate(
            title=r.title,
            ingredients=tuple(i.name for i in r.ingredients),
            steps=tuple(s.strip() for s in r.instructions.splitlines() if s.strip()),
            recipe_id=r.id,
        )
        for r in recipes
    ]


def pantry_keys(items: list[PantryItem], today: dt.date) -> set[str]:
    return {
        units.normalize_name(i.name)
        for i in items
        if i.expires_on is None or i.expires_on >= today
    }


def have_ingredient(name: str, keys: set[str]) -> bool:
    from .ai.matcher import keys_match

    key = units.normalize_name(name)
    return any(keys_match(key, k) for k in keys)


def week_entries(db: Session, user_id: int, monday: dt.date) -> list[MealPlanEntry]:
    sunday = monday + dt.timedelta(days=6)
    stmt = (
        select(MealPlanEntry)
        .where(
            MealPlanEntry.user_id == user_id,
            MealPlanEntry.day >= monday,
            MealPlanEntry.day <= sunday,
        )
        .options(selectinload(MealPlanEntry.recipe).selectinload(Recipe.ingredients))
        .order_by(MealPlanEntry.day, MealPlanEntry.id)
    )
    return list(db.scalars(stmt).all())


def entries_for_cell(
    db: Session, user_id: int, day: dt.date, slot: str
) -> list[MealPlanEntry]:
    stmt = (
        select(MealPlanEntry)
        .where(
            MealPlanEntry.user_id == user_id,
            MealPlanEntry.day == day,
            MealPlanEntry.slot == slot,
        )
        .options(selectinload(MealPlanEntry.recipe))
        .order_by(MealPlanEntry.id)
    )
    return list(db.scalars(stmt).all())


@dataclass
class DayPlan:
    day: dt.date
    cells: dict[str, list[MealPlanEntry]]


def plan_grid(entries: list[MealPlanEntry], monday: dt.date) -> list[DayPlan]:
    grid: dict[dt.date, dict[str, list[MealPlanEntry]]] = {
        monday + dt.timedelta(days=i): {s.value: [] for s in SLOT_ORDER} for i in range(7)
    }
    for e in entries:
        if e.day in grid and e.slot in grid[e.day]:
            grid[e.day][e.slot].append(e)
    return [DayPlan(day=d, cells=cells) for d, cells in grid.items()]


def shopping_for_week(
    db: Session, user_id: int, monday: dt.date, today: dt.date
) -> list[ShoppingItem]:
    needs: list[Need] = []
    for entry in week_entries(db, user_id, monday):
        recipe = entry.recipe
        for ing in recipe.ingredients:
            needs.append(
                Need(
                    name=ing.name,
                    quantity=scale_quantity(ing.quantity, recipe.servings, entry.servings),
                    unit=ing.unit,
                    recipe=recipe.title,
                )
            )
    stock = [
        Stock(name=i.name, quantity=i.quantity, unit=i.unit, expires_on=i.expires_on)
        for i in list_pantry(db, user_id)
    ]
    return build_shopping_list(needs, stock, today)


class RateLimiter:
    """Small in-memory sliding-window limiter (per process) for AI calls."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True
