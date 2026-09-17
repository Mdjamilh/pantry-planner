from __future__ import annotations

import re
from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pantry_planner.ai.service import Assistant
from pantry_planner.config import Settings
from pantry_planner.main import create_app
from tests.conftest import TODAY

CSRF_RE = re.compile(r'<meta name="csrf-token" content="([^"]+)"')


def csrf_of(client: TestClient, path: str = "/login") -> str:
    html = client.get(path).text
    m = CSRF_RE.search(html)
    assert m, f"no csrf meta on {path}"
    return m.group(1)


class Browser:
    """A TestClient wrapper that remembers the CSRF token like a real page."""

    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.token = csrf_of(client)

    def refresh(self, path: str = "/") -> None:
        self.token = csrf_of(self.client, path)

    def get(self, path: str, **kw):  # type: ignore[no-untyped-def]
        return self.client.get(path, **kw)

    def post(self, path: str, data: dict[str, object] | None = None, htmx: bool = False, **kw):  # type: ignore[no-untyped-def]
        payload = {"csrf_token": self.token, **(data or {})}
        headers = kw.pop("headers", {})
        if htmx:
            headers = {"HX-Request": "true", "X-CSRF-Token": self.token, **headers}
        return self.client.post(path, data=payload, headers=headers, **kw)


AppFactory = Callable[..., FastAPI]


@pytest.fixture
def make_app(tmp_path) -> Iterator[AppFactory]:  # type: ignore[no-untyped-def]
    apps: list[FastAPI] = []

    def factory(assistant: Assistant | None = None, **overrides: object) -> FastAPI:
        values: dict[str, object] = {
            "database_url": f"sqlite:///{tmp_path / f'app{len(apps)}.db'}",
            "secret_key": "test-secret",
            "anthropic_api_key": "",
            "demo_mode": False,
            "vercel": "",
        }
        values.update(overrides)
        settings = Settings(**values)  # type: ignore[arg-type]
        app = create_app(settings, assistant=assistant, clock=lambda: TODAY)
        apps.append(app)
        return app

    yield factory
    for app in apps:
        app.state.db.engine.dispose()


@pytest.fixture
def app(make_app: AppFactory) -> FastAPI:
    return make_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, follow_redirects=False) as c:
        yield c


def register(browser: Browser, email: str = "cook@example.com", name: str = "Sam") -> None:
    r = browser.post(
        "/register", {"display_name": name, "email": email, "password": "long-enough-pw"}
    )
    assert r.status_code == 303, r.text
    browser.refresh()


@pytest.fixture
def user(client: TestClient) -> Browser:
    b = Browser(client)
    register(b)
    return b


def add_recipe(browser: Browser, title: str, servings: int, ingredients: str) -> int:
    r = browser.post(
        "/recipes",
        {"title": title, "servings": str(servings), "ingredients": ingredients, "instructions": "Cook."},
    )
    assert r.status_code == 303, r.text
    return int(r.headers["location"].rsplit("/", 1)[1])
