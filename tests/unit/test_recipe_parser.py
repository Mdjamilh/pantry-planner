from pantry_planner.ai.recipe_parser import parse_recipe_text

WITH_HEADINGS = """
Weeknight Tomato Soup
Serves 4

Ingredients
- 2 tbsp olive oil
- 1 onion, chopped
- 2 cloves garlic
- 800 g canned tomatoes
- 500 ml vegetable stock
- Salt and pepper to taste

Method
1. Soften the onion and garlic in the oil.
2. Add tomatoes and stock, simmer for 20 minutes.
3. Blend and season.
"""

NO_HEADINGS = """Quick omelette
3 eggs
30 g grated cheddar
Whisk the eggs with a pinch of salt.
Cook in a hot buttered pan, add the cheese and fold.
"""


def test_parses_sections() -> None:
    r = parse_recipe_text(WITH_HEADINGS)
    assert r.title == "Weeknight Tomato Soup"
    assert r.servings == 4
    assert [i.name for i in r.ingredients] == [
        "olive oil",
        "onion",
        "garlic",
        "canned tomatoes",
        "vegetable stock",
        "Salt and pepper",
    ]
    onion = r.ingredients[1]
    assert (onion.quantity, onion.unit, onion.note) == (1.0, "", "chopped")
    assert r.ingredients[3].unit == "g"
    assert r.steps[0] == "Soften the onion and garlic in the oil."
    assert len(r.steps) == 3


def test_guesses_without_headings() -> None:
    r = parse_recipe_text(NO_HEADINGS)
    assert r.title == "Quick omelette"
    assert r.servings == 2
    assert [(i.name, i.quantity) for i in r.ingredients] == [
        ("eggs", 3.0),
        ("grated cheddar", 30.0),
    ]
    assert len(r.steps) == 2


def test_empty_text_gives_placeholder_title() -> None:
    r = parse_recipe_text("")
    assert r.title == "Imported recipe"
    assert r.ingredients == []


def test_servings_variants() -> None:
    assert parse_recipe_text("Cake\nMakes 12\n").servings == 12
    assert parse_recipe_text("Cake\nServings: 6\n").servings == 6
