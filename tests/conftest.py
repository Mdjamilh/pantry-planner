from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from pantry_planner.db import Database
from pantry_planner.migrate import upgrade_to_head

TODAY = dt.date(2026, 10, 21)  # a Wednesday


@pytest.fixture
def db(tmp_path) -> Iterator[Database]:  # type: ignore[no-untyped-def]
    database = Database(f"sqlite:///{tmp_path / 'test.db'}")
    upgrade_to_head(database.engine)
    yield database
    database.engine.dispose()


@pytest.fixture
def session(db: Database) -> Iterator[Session]:
    with db.sessionmaker() as s:
        yield s
