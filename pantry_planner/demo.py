"""Demo account and sample data.

In demo mode (the public Vercel deployment) the database is a SQLite file in
/tmp. It is wiped and re-seeded on every cold start and every few hours, so the
demo always looks the same. Dates are relative to "today" so there are always
items about to expire.
"""

from __future__ import annotations

import datetime as dt
import time

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from .models import MealPlanEntry, PantryItem, Recipe, RecipeIngredient, User
from .parsing import parse_ingredient_block
from .security import hash_password

DEMO_USER_ID = 1
DEMO_EMAIL = "demo@pantryplanner.dev"
DEMO_PASSWORD = "demo-pantry-2026"  # noqa: S105 - public demo account, shown on the login page
DEMO_NAME = "Demo Cook"

# (name, quantity, unit, days until expiry or None)
PANTRY: list[tuple[str, float, str, int | None]] = [
    ("Baby spinach", 150, "g", 1),
    ("Milk", 1, "l", 2),
    ("Chicken thighs", 500, "g", 2),
    ("Bananas", 3, "", 3),
    ("Bell pepper", 2, "", 0),
    ("Carrots", 4, "", -1),
    ("Tomatoes", 4, "", 4),
    ("Greek yoghurt", 500, "g", 5),
    ("Feta", 200, "g", 6),
    ("Eggs", 6, "", 10),
    ("Cheddar", 250, "g", 14),
    ("Red lentils", 500, "g", None),
    ("Pasta", 1, "kg", None),
    ("Rice", 2, "kg", None),
    ("Rolled oats", 1, "kg", None),
    ("Onions", 3, "", None),
    ("Garlic", 1, "head", None),
    ("Olive oil", 500, "ml", None),
    ("Vegetable stock", 1, "l", None),
]

RECIPES: list[tuple[str, int, str, str]] = [
    (
        "Spinach and feta omelette",
        2,
        """4 eggs
60 g baby spinach
80 g feta, crumbled
1 tbsp olive oil
salt and pepper to taste""",
        "Whisk the eggs with a pinch of salt and pepper.\n"
        "Wilt the spinach in the oil, then pour in the eggs.\n"
        "Scatter over the feta, fold and serve.",
    ),
    (
        "Tomato and red lentil soup",
        4,
        """1 onion, chopped
3 cloves garlic
2 carrots, diced
250 g red lentils
4 tomatoes, chopped
1.2 l vegetable stock
1 tsp cumin""",
        "Soften the onion, garlic and carrot for 5 minutes.\n"
        "Add lentils, tomatoes, cumin and stock.\n"
        "Simmer for 20 minutes, then blend until smooth.",
    ),
    (
        "Chicken and pepper stir-fry",
        2,
        """300 g chicken thighs, sliced
1 bell pepper, sliced
1 onion, sliced
2 cloves garlic
2 tbsp soy sauce
150 g rice""",
        "Cook the rice.\n"
        "Stir-fry the chicken until golden, then add the vegetables.\n"
        "Add soy sauce, toss and serve over the rice.",
    ),
    (
        "Banana oat pancakes",
        2,
        """2 bananas
100 g rolled oats
2 eggs
150 ml milk""",
        "Blend everything into a smooth batter.\n"
        "Cook small pancakes in a hot pan for 2 minutes a side.",
    ),
    (
        "Roasted vegetable pasta",
        4,
        """400 g pasta
2 bell peppers
1 zucchini
1 red onion
200 g cherry tomatoes
3 tbsp olive oil
50 g parmesan""",
        "Roast the chopped vegetables with oil at 200 C for 25 minutes.\n"
        "Boil the pasta.\n"
        "Toss together with the parmesan.",
    ),
    (
        "Greek yoghurt breakfast bowl",
        1,
        """200 g greek yoghurt
40 g rolled oats
1 banana
1 tbsp honey""",
        "Spoon the yoghurt into a bowl.\nTop with oats, sliced banana and honey.",
    ),
]

# (day offset from Monday, slot, recipe index, servings)
PLAN: list[tuple[int, str, int, int]] = [
    (0, "dinner", 2, 2),
    (1, "breakfast", 3, 2),
    (1, "dinner", 1, 4),
    (2, "lunch", 0, 2),
    (3, "dinner", 4, 4),
    (4, "breakfast", 5, 1),
    (5, "dinner", 2, 2),
    (6, "lunch", 1, 2),
]


def week_start(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def wipe(session: Session) -> None:
    for model in (MealPlanEntry, RecipeIngredient, Recipe, PantryItem, User):
        session.execute(delete(model))


def seed(session: Session, today: dt.date) -> User:
    user = User(
        id=DEMO_USER_ID,
        email=DEMO_EMAIL,
        display_name=DEMO_NAME,
        password_hash=hash_password(DEMO_PASSWORD),
    )
    session.add(user)
    session.flush()
    if session.get_bind().dialect.name == "postgresql":
        # We inserted an explicit id, so move the sequence past it.
        session.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('users', 'id'), (SELECT MAX(id) FROM users))"
            )
        )

    for name, qty, unit, days in PANTRY:
        session.add(
            PantryItem(
                user_id=user.id,
                name=name,
                quantity=qty,
                unit=unit,
                expires_on=None if days is None else today + dt.timedelta(days=days),
            )
        )

    recipes: list[Recipe] = []
    for title, servings, ingredients, method in RECIPES:
        recipe = Recipe(
            user_id=user.id, title=title, servings=servings, instructions=method, source="manual"
        )
        for pos, line in enumerate(parse_ingredient_block(ingredients)):
            recipe.ingredients.append(
                RecipeIngredient(
                    position=pos,
                    name=line.name,
                    quantity=line.quantity,
                    unit=line.unit,
                    note=line.note,
                )
            )
        session.add(recipe)
        recipes.append(recipe)
    session.flush()

    monday = week_start(today)
    for offset, slot, idx, servings in PLAN:
        session.add(
            MealPlanEntry(
                user_id=user.id,
                day=monday + dt.timedelta(days=offset),
                slot=slot,
                recipe_id=recipes[idx].id,
                servings=servings,
            )
        )
    session.flush()
    return user


class DemoResetter:
    """Re-seeds the demo database at most every `interval_hours`."""

    def __init__(self, interval_hours: float) -> None:
        self.interval = interval_hours * 3600
        self.last_reset = 0.0

    def reset(self, session: Session, today: dt.date) -> None:
        wipe(session)
        seed(session, today)
        session.commit()
        self.last_reset = time.monotonic()

    def due(self) -> bool:
        return time.monotonic() - self.last_reset >= self.interval
