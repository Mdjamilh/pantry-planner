"""Pydantic schemas shared by the Claude provider and the offline fallback.

The Claude-facing models double as the structured-output schema, so they stay
simple (no numeric bounds); `clean()` methods tidy up and cap what comes back.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

MAX_SUGGESTIONS = 4
MAX_STEPS = 8
MAX_INGREDIENTS = 40


class Suggestion(BaseModel):
    title: str = Field(description="Short dish name, e.g. 'Spinach and feta omelette'.")
    uses: list[str] = Field(description="Pantry items from the list that this dish uses.")
    missing: list[str] = Field(
        description="Ingredients the cook would still need to buy (empty if none)."
    )
    steps: list[str] = Field(description="Two to six short cooking steps.")
    reason: str = Field(description="One sentence on why this dish is a good pick right now.")


class SuggestionList(BaseModel):
    suggestions: list[Suggestion]

    def clean(self) -> SuggestionList:
        cleaned = []
        for s in self.suggestions[:MAX_SUGGESTIONS]:
            title = s.title.strip()[:120]
            if not title:
                continue
            cleaned.append(
                Suggestion(
                    title=title,
                    uses=[u.strip()[:80] for u in s.uses if u.strip()][:12],
                    missing=[m.strip()[:80] for m in s.missing if m.strip()][:12],
                    steps=[st.strip()[:300] for st in s.steps if st.strip()][:MAX_STEPS],
                    reason=s.reason.strip()[:300],
                )
            )
        return SuggestionList(suggestions=cleaned)


class ImportedIngredient(BaseModel):
    name: str = Field(description="Ingredient name without quantity, e.g. 'plain flour'.")
    quantity: float | None = Field(description="Numeric amount, or null if not given.")
    unit: str = Field(
        description="Unit such as g, kg, ml, l, tsp, tbsp, cup, clove, can; empty for counts."
    )
    note: str = Field(description="Preparation note like 'finely chopped', or empty.")


class ImportedRecipe(BaseModel):
    title: str
    servings: int = Field(description="Number of servings; use 2 if the text doesn't say.")
    ingredients: list[ImportedIngredient]
    steps: list[str] = Field(description="Method steps in order, without numbering.")

    def clean(self) -> ImportedRecipe:
        servings = self.servings if 1 <= self.servings <= 50 else 2
        ingredients = [
            ImportedIngredient(
                name=i.name.strip()[:120],
                quantity=i.quantity if i.quantity is None or i.quantity >= 0 else None,
                unit=i.unit.strip()[:20],
                note=i.note.strip()[:160],
            )
            for i in self.ingredients
            if i.name.strip()
        ][:MAX_INGREDIENTS]
        return ImportedRecipe(
            title=(self.title.strip() or "Imported recipe")[:160],
            servings=servings,
            ingredients=ingredients,
            steps=[s.strip() for s in self.steps if s.strip()][:30],
        )


@dataclass(frozen=True)
class PantryFact:
    """The only pantry data the AI ever sees: a name and days until expiry."""

    name: str
    days_left: int | None


@dataclass(frozen=True)
class Candidate:
    """A dish the fallback matcher can recommend (recipe book or built-in)."""

    title: str
    ingredients: tuple[str, ...]
    steps: tuple[str, ...] = ()
    recipe_id: int | None = None


Provider = Literal["claude", "fallback"]


@dataclass
class SuggestionResult:
    suggestions: list[Suggestion]
    provider: Provider
    model: str | None = None
    notice: str | None = None
    # Maps a suggestion title to a recipe in the user's book, when one matches.
    recipe_links: dict[str, int] | None = None


@dataclass
class ImportResult:
    recipe: ImportedRecipe
    provider: Provider
    model: str | None = None
    notice: str | None = None
