"""Form validation shared by the HTML routes."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from .. import units

MAX_QUANTITY = 100_000


@dataclass
class PantryInput:
    name: str = ""
    quantity: float = 0
    unit: str = ""
    expires_on: dt.date | None = None
    errors: dict[str, str] = field(default_factory=dict)
    raw: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def parse_quantity_field(value: str) -> float | None:
    text = value.strip().replace(",", ".")
    if not text:
        return None
    try:
        q = float(text)
    except ValueError:
        return None
    if q != q or q <= 0 or q > MAX_QUANTITY:  # NaN or out of range
        return None
    return q


def validate_pantry(name: str, quantity: str, unit: str, expires_on: str) -> PantryInput:
    data = PantryInput(
        raw={"name": name, "quantity": quantity, "unit": unit, "expires_on": expires_on}
    )
    data.name = " ".join(name.split())
    if not 1 <= len(data.name) <= 120:
        data.errors["name"] = "Give the item a name."
    q = parse_quantity_field(quantity)
    if q is None:
        data.errors["quantity"] = "Enter an amount above zero."
    else:
        data.quantity = q
    data.unit = units.normalize_unit(unit)[:20]
    if expires_on.strip():
        try:
            data.expires_on = dt.date.fromisoformat(expires_on.strip())
        except ValueError:
            data.errors["expires_on"] = "Use a date like 2026-10-31."
    return data
