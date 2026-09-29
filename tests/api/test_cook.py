from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

from pantry_planner.ai.claude import ClaudeProvider
from pantry_planner.ai.schemas import Suggestion, SuggestionList
from pantry_planner.ai.service import Assistant
from pantry_planner.config import Settings
from tests.api.conftest import AppFactory, Browser, add_recipe, register


def test_fallback_answers_without_key(user: Browser) -> None:
    user.post("/pantry", {"name": "Bananas", "quantity": "3", "expires_on": "2026-10-22"})
    user.post("/pantry", {"name": "Oats", "quantity": "500", "unit": "g"})
    page = user.get("/cook").text
    assert "No Anthropic API key is configured" in page
    assert "Bananas" in page  # use-soon sidebar

    r = user.post("/cook/suggest", htmx=True)
    assert r.status_code == 200
    assert 'data-provider="fallback"' in r.text
    assert "Answered by the built-in matcher" in r.text
    assert "Banana oat pancakes" in r.text


def test_suggestions_link_to_recipe_book(user: Browser) -> None:
    user.post("/pantry", {"name": "Lemons", "quantity": "2", "expires_on": "2026-10-22"})
    user.post("/pantry", {"name": "Chicken thighs", "quantity": "500", "unit": "g"})
    rid = add_recipe(user, "Lemon chicken", 2, "500 g chicken thighs\n1 lemon")
    r = user.post("/cook/suggest", htmx=True)
    assert f'href="/recipes/{rid}"' in r.text
    assert "in your recipe book" in r.text


def test_full_page_post_without_htmx(user: Browser) -> None:
    user.post("/pantry", {"name": "Eggs", "quantity": "6"})
    r = user.post("/cook/suggest")
    assert r.status_code == 200
    assert "What can I cook?" in r.text


class StubMessages:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        out = SuggestionList(
            suggestions=[
                Suggestion(
                    title="Spinach dal",
                    uses=["Spinach"],
                    missing=["Red lentils"],
                    steps=["Cook lentils", "Stir in spinach"],
                    reason="Spinach expires tomorrow.",
                )
            ]
        )
        return SimpleNamespace(parsed_output=out, stop_reason="end_turn")


def test_claude_answers_when_key_is_set(make_app: AppFactory) -> None:
    messages = StubMessages()
    settings = Settings(anthropic_api_key="sk-test")
    provider = ClaudeProvider(SimpleNamespace(messages=messages), "claude-haiku-5-5")  # type: ignore[arg-type]
    app = make_app(assistant=Assistant(settings, provider=provider), anthropic_api_key="sk-test")
    with TestClient(app, follow_redirects=False) as client:
        b = Browser(client)
        register(b, email="private.person@example.com", name="Private Person")
        b.post(
            "/pantry",
            {"name": "Spinach", "quantity": "100", "unit": "g", "expires_on": "2026-10-22"},
        )
        page = b.get("/cook").text
        assert "Claude (claude-haiku-5-5) answers" in page

        r = b.post("/cook/suggest", htmx=True)
        assert 'data-provider="claude"' in r.text
        assert "Answered by Claude" in r.text
        assert "Spinach dal" in r.text
        assert "Red lentils" in r.text

    sent = str(messages.calls[0])
    assert "Spinach (expires in 1 days)" in sent
    assert "private.person" not in sent
    assert "Private Person" not in sent
    assert "100" not in sent  # quantities are not needed, so not sent


def test_ai_rate_limit(make_app: AppFactory) -> None:
    settings = Settings(anthropic_api_key="sk-test")
    provider = ClaudeProvider(SimpleNamespace(messages=StubMessages()), "m")  # type: ignore[arg-type]
    app = make_app(assistant=Assistant(settings, provider=provider), anthropic_api_key="sk-test")
    with TestClient(app, follow_redirects=False) as client:
        b = Browser(client)
        register(b)
        b.post("/pantry", {"name": "Spinach", "quantity": "1"})
        texts = [b.post("/cook/suggest", htmx=True).text for _ in range(13)]
    assert "Answered by Claude" in texts[0]
    assert "a lot of suggestions" in texts[-1]


def test_suggest_requires_login(client: TestClient) -> None:
    b = Browser(client)
    r = b.post("/cook/suggest", htmx=True)
    assert r.status_code == 204
    assert r.headers["hx-redirect"] == "/login"
