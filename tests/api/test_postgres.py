"""Runs only when TEST_DATABASE_URL points at a Postgres database (CI does this)."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from pantry_planner import demo, services
from pantry_planner.config import Settings
from pantry_planner.db import Database
from pantry_planner.main import create_app
from pantry_planner.migrate import upgrade_to_head
from tests.api.conftest import Browser, add_recipe, register
from tests.conftest import TODAY

URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL.startswith("postgres"), reason="needs TEST_DATABASE_URL")


def _reset_schema(database: Database) -> None:
    with database.engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture
def pg() -> Iterator[Database]:
    database = Database(Settings(database_url=URL).database_url)
    _reset_schema(database)
    upgrade_to_head(database.engine)
    yield database
    database.engine.dispose()


def test_migrations_and_demo_seed(pg: Database) -> None:
    with pg.sessionmaker() as s:
        demo.seed(s, TODAY)
        s.commit()
        items = services.shopping_for_week(s, demo.DEMO_USER_ID, demo.week_start(TODAY), TODAY)
    assert items, "demo plan should need some shopping"


def test_sequence_moves_past_demo_user(pg: Database) -> None:
    app = create_app(
        Settings(database_url=URL, secret_key="t", demo_mode=True, vercel=""),
        clock=lambda: TODAY,
    )
    with TestClient(app, follow_redirects=False) as client:
        b = Browser(client)
        register(b, "pg@example.com", "Pg")  # would collide with id 1 without setval
        rid = add_recipe(b, "Pg soup", 2, "1 l stock\n2 carrots")
        assert b.get(f"/recipes/{rid}").status_code == 200
        r = b.post("/plan", {"day": TODAY.isoformat(), "slot": "lunch", "recipe_id": str(rid)})
        assert r.status_code == 303
        names = {i["name"] for i in b.get("/api/shopping-list").json()["items"]}
        assert names == {"Stock", "Carrots"}
    app.state.db.engine.dispose()
