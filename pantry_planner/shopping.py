"""Shopping list: what the meal plan needs minus what the pantry already has.

Everything here works on plain dataclasses, so it is easy to test without a
database. Amounts are compared in base units (grams, millilitres, pieces), so
"1 kg flour" in the pantry covers "250 g flour" in a recipe. Mass and volume
are never mixed: we don't guess densities, we flag the mismatch instead.
"""

from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from . import units

EPSILON = 1e-6


@dataclass(frozen=True)
class Need:
    """One ingredient required by one planned meal (already scaled)."""

    name: str
    quantity: float | None
    unit: str
    recipe: str


@dataclass(frozen=True)
class Stock:
    """One pantry item."""

    name: str
    quantity: float
    unit: str
    expires_on: dt.date | None = None


@dataclass
class ShoppingItem:
    key: str
    name: str
    quantity: float | None
    unit: str
    recipes: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def amount_text(self) -> str:
        if self.quantity is None:
            return ""
        return units.format_amount(self.quantity, self.unit)


def scale_quantity(
    quantity: float | None, recipe_servings: int, planned_servings: int
) -> float | None:
    if quantity is None:
        return None
    if recipe_servings <= 0:
        return quantity
    return quantity * planned_servings / recipe_servings


def usable_stock(stock: Iterable[Stock], today: dt.date) -> list[Stock]:
    """Expired items don't count towards what we have."""
    return [s for s in stock if s.expires_on is None or s.expires_on >= today]


# Recipes often use spoons and cups for small amounts; keep those units on the
# list instead of turning "1 tbsp honey" into "14.8 ml".
KITCHEN_UNITS = {"tsp", "tbsp", "cup", "oz", "lb", "fl oz"}


def _capitalise(name: str) -> str:
    return name[:1].upper() + name[1:]


def present(dim: str, base_amount: float, used: set[str]) -> tuple[float, str]:
    """Pick the unit to show a remaining amount in.

    Countable things are rounded up (you can't buy half an onion), and when
    every recipe used the same spoon or cup unit we keep that unit.
    """
    if len(used) == 1:
        (only,) = used
        if only in KITCHEN_UNITS:
            return round(base_amount / units.UNITS[only][1], 2), only
    if dim == units.COUNT or dim.startswith("unit:"):
        qty, unit = units.humanize(dim, base_amount)
        return float(math.ceil(qty - 1e-9)), unit
    return units.humanize(dim, base_amount)


def build_shopping_list(
    needs: Iterable[Need], stock: Iterable[Stock], today: dt.date
) -> list[ShoppingItem]:
    required: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    used_units: dict[tuple[str, str], set[str]] = defaultdict(set)
    unquantified: set[str] = set()
    display: dict[str, str] = {}
    recipes: dict[str, list[str]] = defaultdict(list)

    for need in needs:
        key = units.normalize_name(need.name)
        display.setdefault(key, _capitalise(need.name.strip()))
        if need.recipe not in recipes[key]:
            recipes[key].append(need.recipe)
        if need.quantity is None:
            unquantified.add(key)
            continue
        dim, base = units.to_base(need.quantity, need.unit)
        required[key][dim] += base
        used_units[(key, dim)].add(units.normalize_unit(need.unit))

    available: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for item in usable_stock(stock, today):
        key = units.normalize_name(item.name)
        dim, base = units.to_base(item.quantity, item.unit)
        available[key][dim] += base

    items: list[ShoppingItem] = []
    for key in sorted(set(required) | unquantified):
        have = available.get(key, {})
        for dim, base_needed in sorted(required.get(key, {}).items()):
            remaining = base_needed - have.get(dim, 0.0)
            if remaining <= EPSILON * max(1.0, base_needed):
                continue
            qty, unit = present(dim, remaining, used_units[(key, dim)])
            note = ""
            if dim in have:
                got_qty, got_unit = units.humanize(dim, have[dim])
                note = f"you have {units.format_amount(got_qty, got_unit)}"
            else:
                other = [d for d in have if d != dim]
                if other:
                    got_qty, got_unit = units.humanize(other[0], have[other[0]])
                    note = (
                        f"pantry has {units.format_amount(got_qty, got_unit)}, units don't compare"
                    )
            items.append(
                ShoppingItem(
                    key=key,
                    name=display[key],
                    quantity=qty,
                    unit=unit,
                    recipes=recipes[key],
                    note=note,
                )
            )
        if key in unquantified and key not in required and not have:
            items.append(
                ShoppingItem(
                    key=key,
                    name=display[key],
                    quantity=None,
                    unit="",
                    recipes=recipes[key],
                    note="amount not specified",
                )
            )
    return items
