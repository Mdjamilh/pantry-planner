from types import SimpleNamespace
from typing import Any

import pytest

from pantry_planner.ai.claude import ClaudeProvider, describe_pantry
from pantry_planner.ai.schemas import (
    Candidate,
    ImportedIngredient,
    ImportedRecipe,
    PantryFact,
    Suggestion,
    SuggestionList,
)
from pantry_planner.ai.service import Assistant
from pantry_planner.config import Settings


class FakeMessages:
    def __init__(self, result: Any = None, error: Exception | None = None, stop: str = "end_turn"):
        self.result = result
        self.error = error
        self.stop = stop
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(parsed_output=self.result, stop_reason=self.stop)


def make(messages: FakeMessages) -> Assistant:
    provider = ClaudeProvider(SimpleNamespace(messages=messages), "claude-haiku-5-5")  # type: ignore[arg-type]
    return Assistant(Settings(anthropic_api_key="test-key"), provider=provider)


FACTS = [PantryFact("Spinach", 1), PantryFact("Eggs", 6), PantryFact("Old milk", -1)]


def test_claude_answers_when_configured() -> None:
    answer = SuggestionList(
        suggestions=[
            Suggestion(
                title="Spinach omelette",
                uses=["Spinach", "Eggs"],
                missing=[],
                steps=["Whisk", "Cook"],
                reason="Spinach is about to turn.",
            )
        ]
    )
    messages = FakeMessages(answer)
    book = [Candidate("Spinach omelette", ("egg", "spinach"), recipe_id=9)]
    result = make(messages).suggest(FACTS, book)
    assert result.provider == "claude"
    assert result.model == "claude-haiku-5-5"
    assert result.suggestions[0].title == "Spinach omelette"
    assert result.recipe_links == {"Spinach omelette": 9}


def test_only_ingredient_names_and_expiry_are_sent() -> None:
    messages = FakeMessages(SuggestionList(suggestions=[]))
    make(messages).suggest(FACTS, [Candidate("Secret family recipe", ("x",), recipe_id=1)])
    call = messages.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["output_format"] is SuggestionList
    content = call["messages"][0]["content"]
    assert content == ("Pantry items:\n- Spinach (expires in 1 days)\n- Eggs (expires in 6 days)")
    # Expired items and recipe-book titles are not sent.
    assert "Old milk" not in content
    assert "Secret" not in str(call)


def test_falls_back_on_api_error() -> None:
    messages = FakeMessages(error=RuntimeError("boom"))
    result = make(messages).suggest(FACTS, [])
    assert result.provider == "fallback"
    assert result.notice is not None
    assert "built-in matcher" in result.notice


def test_falls_back_on_refusal() -> None:
    messages = FakeMessages(SuggestionList(suggestions=[]), stop="refusal")
    result = make(messages).suggest(FACTS, [])
    assert result.provider == "fallback"
    assert result.notice is not None
    assert "declined" in result.notice


def test_no_key_uses_matcher_without_calling_claude() -> None:
    assistant = Assistant(Settings(anthropic_api_key=""))
    assert assistant.provider is None
    result = assistant.suggest([PantryFact("banana", 1), PantryFact("oats", None)], [])
    assert result.provider == "fallback"
    assert result.notice is None
    assert result.suggestions[0].title == "Banana oat pancakes"


def test_import_with_claude_cleans_output() -> None:
    raw = ImportedRecipe(
        title="  Pancakes ",
        servings=0,
        ingredients=[
            ImportedIngredient(name="flour", quantity=200, unit="g", note=""),
            ImportedIngredient(name="  ", quantity=1, unit="", note=""),
        ],
        steps=["Mix", ""],
    )
    messages = FakeMessages(raw)
    result = make(messages).import_recipe("Pancakes\n200 g flour\nMix")
    assert result.provider == "claude"
    assert result.recipe.title == "Pancakes"
    assert result.recipe.servings == 2
    assert [i.name for i in result.recipe.ingredients] == ["flour"]
    assert result.recipe.steps == ["Mix"]
    assert messages.calls[0]["messages"][0]["content"].startswith("<recipe>")


def test_import_falls_back_to_parser() -> None:
    result = make(FakeMessages(error=TimeoutError())).import_recipe("Toast\n2 slices bread\n")
    assert result.provider == "fallback"
    assert result.recipe.ingredients[0].unit == "slice"


def test_import_text_is_truncated() -> None:
    messages = FakeMessages(ImportedRecipe(title="x", servings=2, ingredients=[], steps=[]))
    make(messages).import_recipe("a" * 20000)
    assert len(messages.calls[0]["messages"][0]["content"]) < 8100


@pytest.mark.parametrize(
    ("fact", "line"),
    [
        (PantryFact("rice", None), "- rice (no expiry date)"),
        (PantryFact("milk", -2), "- milk (expired 2 days ago)"),
    ],
)
def test_describe_pantry(fact: PantryFact, line: str) -> None:
    assert describe_pantry([fact]) == line
