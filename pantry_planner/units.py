"""Units and ingredient names.

Quantities are converted to a base unit per dimension so that "1 kg flour" in
the pantry can be subtracted from "250 g flour" in a recipe:

* mass   -> grams
* volume -> millilitres
* count  -> pieces

Units we don't know (clove, can, bunch, ...) form their own dimension, so
"2 cloves garlic" only combines with other cloves of garlic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MASS = "mass"
VOLUME = "volume"
COUNT = "count"

# canonical unit -> (dimension, factor to base unit)
UNITS: dict[str, tuple[str, float]] = {
    "g": (MASS, 1.0),
    "kg": (MASS, 1000.0),
    "oz": (MASS, 28.349523125),
    "lb": (MASS, 453.59237),
    "ml": (VOLUME, 1.0),
    "l": (VOLUME, 1000.0),
    "tsp": (VOLUME, 4.92892159375),
    "tbsp": (VOLUME, 14.78676478125),
    "cup": (VOLUME, 236.5882365),
    "fl oz": (VOLUME, 29.5735295625),
    "pc": (COUNT, 1.0),
    "dozen": (COUNT, 12.0),
}

ALIASES: dict[str, str] = {
    "": "pc",
    "gram": "g",
    "grams": "g",
    "gr": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "kgs": "kg",
    "ounce": "oz",
    "ounces": "oz",
    "pound": "lb",
    "pounds": "lb",
    "lbs": "lb",
    "millilitre": "ml",
    "milliliter": "ml",
    "millilitres": "ml",
    "milliliters": "ml",
    "litre": "l",
    "liter": "l",
    "litres": "l",
    "liters": "l",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tbs": "tbsp",
    "cups": "cup",
    "fluid ounce": "fl oz",
    "fluid ounces": "fl oz",
    "floz": "fl oz",
    "piece": "pc",
    "pieces": "pc",
    "pcs": "pc",
    "each": "pc",
    "ea": "pc",
    "whole": "pc",
    "x": "pc",
}

# Units that are not convertible but still worth recognising (and singularising).
OTHER_UNITS: dict[str, str] = {
    "clove": "clove",
    "cloves": "clove",
    "can": "can",
    "cans": "can",
    "tin": "can",
    "tins": "can",
    "jar": "jar",
    "jars": "jar",
    "bunch": "bunch",
    "bunches": "bunch",
    "pinch": "pinch",
    "pinches": "pinch",
    "slice": "slice",
    "slices": "slice",
    "pack": "pack",
    "packs": "pack",
    "packet": "pack",
    "packets": "pack",
    "stick": "stick",
    "sticks": "stick",
    "sprig": "sprig",
    "sprigs": "sprig",
    "head": "head",
    "heads": "head",
    "bag": "bag",
    "bags": "bag",
    "handful": "handful",
    "handfuls": "handful",
}


def normalize_unit(unit: str | None) -> str:
    """Return the canonical spelling of a unit ("Tablespoons" -> "tbsp")."""
    u = (unit or "").strip().lower().rstrip(".")
    u = re.sub(r"\s+", " ", u)
    if u in UNITS:
        return u
    if u in ALIASES:
        return ALIASES[u]
    if u in OTHER_UNITS:
        return OTHER_UNITS[u]
    return u


def is_known_unit(word: str) -> bool:
    w = word.strip().lower().rstrip(".")
    return w in UNITS or (w in ALIASES and w != "") or w in OTHER_UNITS


def dimension_of(unit: str) -> str:
    u = normalize_unit(unit)
    if u in UNITS:
        return UNITS[u][0]
    return f"unit:{u}"


def to_base(quantity: float, unit: str) -> tuple[str, float]:
    """Convert to the dimension's base unit. Returns (dimension, amount)."""
    u = normalize_unit(unit)
    if u in UNITS:
        dim, factor = UNITS[u]
        return dim, quantity * factor
    return f"unit:{u}", quantity


def convert(quantity: float, from_unit: str, to_unit: str) -> float | None:
    """Convert between two units, or None when the dimensions differ."""
    d1, base = to_base(quantity, from_unit)
    d2, factor = to_base(1.0, to_unit)
    if d1 != d2 or factor == 0:
        return None
    return base / factor


def _round_nicely(value: float) -> float:
    if value >= 100:
        return float(round(value))
    if value >= 10:
        return round(value, 1)
    return round(value, 2)


def humanize(dimension: str, base_amount: float) -> tuple[float, str]:
    """Pick a readable unit for an amount in base units (1500 g -> 1.5 kg)."""
    if dimension == MASS:
        if base_amount >= 1000:
            return _round_nicely(base_amount / 1000), "kg"
        return _round_nicely(base_amount), "g"
    if dimension == VOLUME:
        if base_amount >= 1000:
            return _round_nicely(base_amount / 1000), "l"
        return _round_nicely(base_amount), "ml"
    if dimension == COUNT:
        return _round_nicely(base_amount), "pc"
    return _round_nicely(base_amount), dimension.removeprefix("unit:")


def format_quantity(quantity: float | None) -> str:
    """1.0 -> "1", 0.5 -> "0.5", 0.333 -> "0.33"."""
    if quantity is None:
        return ""
    q = _round_nicely(quantity)
    if q == int(q):
        return str(int(q))
    return f"{q:g}"


def format_amount(quantity: float | None, unit: str) -> str:
    qty = format_quantity(quantity)
    u = normalize_unit(unit)
    if u == "pc":
        return qty
    return f"{qty} {u}".strip()


# --- ingredient names -------------------------------------------------------

_IRREGULAR = {
    "leaves": "leaf",
    "potatoes": "potato",
    "tomatoes": "tomato",
    "mangoes": "mango",
    "knives": "knife",
    "loaves": "loaf",
    "halves": "half",
}
_NO_SINGULAR = {
    "asparagus",
    "couscous",
    "hummus",
    "molasses",
    "swiss",
    "chives",
    "grass",
    "lettuce",
    "rice",
    "oats",
    "peas",
    "lentils",
    "chickpeas",
    "noodles",
    "greens",
    "brussels",
    "citrus",
    "octopus",
}


def singularize(word: str) -> str:
    w = word.lower()
    if w in _NO_SINGULAR or len(w) <= 3:
        return w
    if w in _IRREGULAR:
        return _IRREGULAR[w]
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith(("ches", "shes", "sses", "xes", "zes")):
        return w[:-2]
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


_DROP_WORDS = {
    "fresh",
    "large",
    "small",
    "medium",
    "ripe",
    "chopped",
    "diced",
    "sliced",
    "minced",
    "grated",
    "of",
    "organic",
    "free-range",
    "raw",
}


def normalize_name(name: str) -> str:
    """Key used to match ingredients ("2 Large Ripe Tomatoes" -> "tomato")."""
    text = name.lower()
    text = re.sub(r"\(.*?\)", " ", text)
    text = text.split(",")[0]
    words = re.findall(r"[a-z][a-z\-']*", text)
    words = [w for w in words if w not in _DROP_WORDS]
    if not words:
        return name.strip().lower()
    words[-1] = singularize(words[-1])
    return " ".join(words)


@dataclass(frozen=True)
class Amount:
    dimension: str
    base: float

    def readable(self) -> tuple[float, str]:
        return humanize(self.dimension, self.base)
