"""Rule-based "What can I cook?" matcher.

Used when no Anthropic API key is configured, or when the Claude call fails.
It scores each candidate dish (the user's recipes plus a small built-in
catalog) by how much of it the pantry already covers, weighting items that are
about to expire more heavily. Same input always gives the same output.
"""

from __future__ import annotations

from collections.abc import Iterable

from .. import units
from .catalog import CATALOG
from .schemas import MAX_SUGGESTIONS, Candidate, PantryFact, Suggestion

# Things most kitchens have; they never count as "missing" or as a match.
STAPLES = frozenset(
    {
        "salt",
        "pepper",
        "black pepper",
        "salt and pepper",
        "water",
        "oil",
        "olive oil",
        "vegetable oil",
        "sugar",
    }
)


def keys_match(a: str, b: str) -> bool:
    """Match "red onion" with "onion" in either direction."""
    if a == b:
        return True
    return a.endswith(" " + b) or b.endswith(" " + a)


def _weight(days_left: int | None, soon_days: int) -> float:
    if days_left is None:
        return 1.0
    if days_left < 0:
        return 0.0  # expired: don't build a suggestion around it
    if days_left <= soon_days:
        return 3.0
    if days_left <= 7:
        return 1.5
    return 1.0


def _display(name: str) -> str:
    return name[:1].upper() + name[1:]


def suggest(
    pantry: Iterable[PantryFact],
    candidates: Iterable[Candidate],
    *,
    soon_days: int = 3,
    include_catalog: bool = True,
    limit: int = MAX_SUGGESTIONS,
) -> list[tuple[Suggestion, int | None]]:
    """Return up to `limit` suggestions, each with an optional recipe id."""
    facts = [(units.normalize_name(p.name), p) for p in pantry]
    pool = list(candidates) + (list(CATALOG) if include_catalog else [])

    scored: list[tuple[float, int, Suggestion, int | None]] = []
    seen_titles: set[str] = set()
    for order, cand in enumerate(pool):
        title_key = cand.title.strip().lower()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        ingredients = [units.normalize_name(i) for i in cand.ingredients]
        ingredients = [i for i in dict.fromkeys(ingredients) if i not in STAPLES]
        if not ingredients:
            continue

        uses: list[str] = []
        missing: list[str] = []
        score = 0.0
        soon_hits = 0
        for ing in ingredients:
            best: tuple[float, PantryFact] | None = None
            for key, fact in facts:
                if keys_match(ing, key):
                    w = _weight(fact.days_left, soon_days)
                    if w > 0 and (best is None or w > best[0]):
                        best = (w, fact)
            if best is None:
                missing.append(ing)
                continue
            score += best[0]
            uses.append(best[1].name)
            if best[0] >= 3.0:
                soon_hits += 1

        coverage = len(uses) / len(ingredients)
        if not uses or coverage < 0.4:
            continue
        score += 4 * coverage - 0.5 * len(missing)

        if soon_hits:
            reason = (
                f"Uses {soon_hits} item{'s' if soon_hits != 1 else ''} that expire soon "
                f"and you have {len(uses)} of {len(ingredients)} ingredients."
            )
        else:
            reason = f"You have {len(uses)} of {len(ingredients)} ingredients."
        suggestion = Suggestion(
            title=cand.title,
            uses=list(dict.fromkeys(uses)),
            missing=[_display(m) for m in missing],
            steps=list(cand.steps),
            reason=reason,
        )
        # Ties: recipe-book entries first (they come earlier in the pool).
        scored.append((score, -order, suggestion, cand.recipe_id))

    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [(s, rid) for _, _, s, rid in scored[:limit]]
