"""Offline recipe importer: turn pasted recipe text into structured data.

Handles the common shapes recipes are copied in: a title line, an optional
"Serves 4", an "Ingredients" section and a "Method" section. When there are no
headings it guesses line by line: short lines that start with a quantity are
ingredients, longer sentences are steps.
"""

from __future__ import annotations

import re

from ..parsing import parse_ingredient_line, parse_quantity
from .schemas import ImportedIngredient, ImportedRecipe

_INGREDIENT_HEAD = re.compile(r"^\s*(ingredients?|you will need|shopping list)\s*:?\s*$", re.I)
_METHOD_HEAD = re.compile(
    r"^\s*(method|instructions?|directions?|steps?|preparation|how to make( it)?)\s*:?\s*$",
    re.I,
)
_SERVES = re.compile(r"\b(?:serves|servings?|makes|yield|portions?)\b\D{0,12}(\d{1,2})", re.I)
_STEP_PREFIX = re.compile(r"^\s*(?:step\s*)?\d+\s*[.):-]\s*|^\s*[-*•]\s*", re.I)


def _looks_like_ingredient(line: str) -> bool:
    qty, _ = parse_quantity(re.sub(r"^\s*[-*•]\s*", "", line))
    return qty is not None and len(line) <= 80 and not line.rstrip().endswith(".")


def parse_recipe_text(text: str) -> ImportedRecipe:
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n")]
    title = ""
    servings = 2
    ingredients: list[ImportedIngredient] = []
    steps: list[str] = []
    section: str | None = None

    for raw in lines:
        if not raw:
            continue
        m = _SERVES.search(raw)
        if m and len(raw) <= 40:
            servings = int(m.group(1)) or 2
            continue
        if _INGREDIENT_HEAD.match(raw):
            section = "ingredients"
            continue
        if _METHOD_HEAD.match(raw):
            section = "method"
            continue
        if not title and section is None and not _looks_like_ingredient(raw):
            title = raw.lstrip("# ").strip()
            continue

        if section == "ingredients" or (section is None and _looks_like_ingredient(raw)):
            parsed = parse_ingredient_line(raw)
            if parsed:
                ingredients.append(
                    ImportedIngredient(
                        name=parsed.name,
                        quantity=parsed.quantity,
                        unit=parsed.unit,
                        note=parsed.note,
                    )
                )
            continue

        step = _STEP_PREFIX.sub("", raw).strip()
        if step:
            steps.append(step)

    return ImportedRecipe(
        title=title or "Imported recipe",
        servings=servings,
        ingredients=ingredients,
        steps=steps,
    ).clean()
