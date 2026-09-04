import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pantry_planner import demo
from pantry_planner.models import MealPlanEntry, PantryItem, Recipe, User
from tests.conftest import TODAY


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_seed_creates_demo_account_and_data(session: Session) -> None:
    user = demo.seed(session, TODAY)
    session.commit()
    assert user.id == demo.DEMO_USER_ID
    assert count(session, PantryItem) == len(demo.PANTRY)
    assert count(session, Recipe) == len(demo.RECIPES)
    assert count(session, MealPlanEntry) == len(demo.PLAN)
    spinach = session.scalars(select(PantryItem).where(PantryItem.name == "Baby spinach")).one()
    assert spinach.expires_on == TODAY + dt.timedelta(days=1)


def test_plan_is_in_the_current_week(session: Session) -> None:
    demo.seed(session, TODAY)
    days = session.scalars(select(MealPlanEntry.day)).all()
    monday = demo.week_start(TODAY)
    assert monday == dt.date(2026, 10, 19)
    assert all(monday <= d <= monday + dt.timedelta(days=6) for d in days)


def test_reset_wipes_other_users(session: Session) -> None:
    resetter = demo.DemoResetter(interval_hours=6)
    assert resetter.due()
    resetter.reset(session, TODAY)
    session.add(User(email="x@example.com", display_name="X", password_hash="h"))
    session.commit()
    resetter.reset(session, TODAY)
    assert count(session, User) == 1
    assert not resetter.due()
