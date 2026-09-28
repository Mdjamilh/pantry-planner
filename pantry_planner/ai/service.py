"""Chooses who answers: Claude when a key is configured, the local rules otherwise.

Any Claude failure falls back to the local answer, and the result always says
which one answered so the UI can show it.
"""

from __future__ import annotations

import logging

from ..config import Settings
from . import matcher
from .claude import AIUnavailable, ClaudeProvider, make_client
from .recipe_parser import parse_recipe_text
from .schemas import Candidate, ImportResult, PantryFact, Suggestion, SuggestionResult

log = logging.getLogger(__name__)


class Assistant:
    def __init__(self, settings: Settings, provider: ClaudeProvider | None = None) -> None:
        self.settings = settings
        self._provider = provider

    @property
    def provider(self) -> ClaudeProvider | None:
        if self._provider is None and self.settings.ai_enabled:
            client = make_client(self.settings.anthropic_api_key, self.settings.ai_timeout_seconds)
            self._provider = ClaudeProvider(client, self.settings.anthropic_model)
        return self._provider

    def suggest(self, facts: list[PantryFact], book: list[Candidate]) -> SuggestionResult:
        provider = self.provider
        notice = None
        if provider is not None:
            usable = [f for f in facts if f.days_left is None or f.days_left >= 0]
            try:
                result = provider.suggest(usable)
                return SuggestionResult(
                    suggestions=result.suggestions,
                    provider="claude",
                    model=provider.model,
                    recipe_links=_link_titles(result.suggestions, book),
                )
            except AIUnavailable as exc:
                log.warning("Claude suggestions failed: %s", exc)
                notice = f"Claude was unavailable ({exc}), so the built-in matcher answered."

        ranked = matcher.suggest(facts, book, soon_days=self.settings.expiring_soon_days)
        links = {s.title: rid for s, rid in ranked if rid is not None}
        return SuggestionResult(
            suggestions=[s for s, _ in ranked],
            provider="fallback",
            notice=notice,
            recipe_links=links,
        )

    def import_recipe(self, text: str) -> ImportResult:
        provider = self.provider
        notice = None
        if provider is not None:
            try:
                return ImportResult(
                    recipe=provider.import_recipe(text), provider="claude", model=provider.model
                )
            except AIUnavailable as exc:
                log.warning("Claude import failed: %s", exc)
                notice = f"Claude was unavailable ({exc}), so the built-in parser answered."
        return ImportResult(recipe=parse_recipe_text(text), provider="fallback", notice=notice)


def _link_titles(suggestions: list[Suggestion], book: list[Candidate]) -> dict[str, int]:
    by_title = {c.title.strip().lower(): c.recipe_id for c in book if c.recipe_id is not None}
    links: dict[str, int] = {}
    for s in suggestions:
        rid = by_title.get(s.title.strip().lower())
        if rid is not None:
            links[s.title] = rid
    return links
