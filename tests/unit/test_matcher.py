from pantry_planner.ai.matcher import keys_match, suggest
from pantry_planner.ai.schemas import Candidate, PantryFact


def test_keys_match_on_last_words() -> None:
    assert keys_match("red onion", "onion")
    assert keys_match("onion", "red onion")
    assert not keys_match("onion", "onion powder")
    assert not keys_match("pea", "chickpeas")


def test_prefers_dishes_using_expiring_items() -> None:
    pantry = [
        PantryFact("Spinach", 1),
        PantryFact("Eggs", 10),
        PantryFact("Pasta", None),
        PantryFact("Tomatoes", 20),
    ]
    results = suggest(pantry, [])
    titles = [s.title for s, _ in results]
    assert titles[0] == "Spinach and cheese frittata"
    assert "Spinach" in results[0][0].uses
    assert "expire soon" in results[0][0].reason


def test_recipe_book_entries_carry_their_id() -> None:
    pantry = [PantryFact("chicken thigh", 2), PantryFact("lemon", 5)]
    book = [Candidate("Lemon chicken", ("chicken thighs", "lemons", "salt"), recipe_id=42)]
    results = suggest(pantry, book)
    assert results[0][0].title == "Lemon chicken"
    assert results[0][1] == 42
    assert results[0][0].missing == []


def test_expired_items_are_ignored() -> None:
    pantry = [PantryFact("banana", -2), PantryFact("oats", None)]
    results = suggest(pantry, [], include_catalog=True)
    for s, _ in results:
        assert "banana" not in s.uses


def test_low_coverage_dishes_are_skipped() -> None:
    pantry = [PantryFact("garlic", None)]
    assert suggest(pantry, [], include_catalog=True) == []


def test_staples_never_count_as_missing() -> None:
    book = [Candidate("Boiled eggs", ("eggs", "salt", "water"))]
    results = suggest([PantryFact("egg", 3)], book, include_catalog=False)
    assert results[0][0].missing == []


def test_is_deterministic_and_limited() -> None:
    pantry = [PantryFact(n, 2) for n in ["egg", "onion", "tomato", "rice", "carrot", "milk"]]
    first = suggest(pantry, [], limit=3)
    second = suggest(pantry, [], limit=3)
    assert first == second
    assert len(first) == 3


def test_duplicate_titles_collapse() -> None:
    book = [Candidate("Greek salad", ("tomato", "feta"), recipe_id=7)]
    pantry = [PantryFact("tomato", 1), PantryFact("feta", 1)]
    results = suggest(pantry, book)
    titles = [s.title for s, _ in results]
    assert titles.count("Greek salad") == 1
    assert dict((s.title, rid) for s, rid in results)["Greek salad"] == 7
