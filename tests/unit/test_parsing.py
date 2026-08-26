import pytest

from pantry_planner.parsing import (
    IngredientLine,
    parse_ingredient_block,
    parse_ingredient_line,
    parse_quantity,
)


@pytest.mark.parametrize(
    ("text", "qty", "rest"),
    [
        ("2 eggs", 2.0, "eggs"),
        ("1.5 kg potatoes", 1.5, "kg potatoes"),
        ("1/2 cup milk", 0.5, "cup milk"),
        ("1 1/2 cups flour", 1.5, "cups flour"),
        ("½ tsp salt", 0.5, "tsp salt"),
        ("1½ cups rice", 1.5, "cups rice"),
        ("2-3 carrots", 3.0, "carrots"),
        ("2 to 4 cloves garlic", 4.0, "cloves garlic"),
        ("a pinch of salt", 1.0, "pinch of salt"),
        ("salt", None, "salt"),
        ("200g flour", 200.0, "g flour"),
    ],
)
def test_parse_quantity(text: str, qty: float | None, rest: str) -> None:
    assert parse_quantity(text) == (qty, rest)


def test_full_line_with_unit_and_note() -> None:
    line = parse_ingredient_line("- 1 1/2 cups plain flour, sifted")
    assert line == IngredientLine(name="plain flour", quantity=1.5, unit="cup", note="sifted")


def test_glued_unit() -> None:
    line = parse_ingredient_line("250g dried spaghetti")
    assert line is not None
    assert (line.quantity, line.unit, line.name) == (250.0, "g", "dried spaghetti")


def test_two_word_unit_and_of() -> None:
    line = parse_ingredient_line("4 fl oz of cream")
    assert line is not None
    assert (line.quantity, line.unit, line.name) == (4.0, "fl oz", "cream")


def test_count_items_have_no_unit() -> None:
    line = parse_ingredient_line("3 large eggs")
    assert line is not None
    assert (line.quantity, line.unit, line.name) == (3.0, "", "large eggs")


def test_to_taste_and_parentheses() -> None:
    line = parse_ingredient_line("Salt and pepper to taste")
    assert line == IngredientLine(name="Salt and pepper", note="to taste")
    line = parse_ingredient_line("1 can (400 g) chopped tomatoes")
    assert line is not None
    assert (line.quantity, line.unit, line.name, line.note) == (
        1.0,
        "can",
        "chopped tomatoes",
        "400 g",
    )


def test_numbered_list_marker_is_not_a_quantity() -> None:
    line = parse_ingredient_line("1. 2 onions")
    assert line is not None
    assert (line.quantity, line.name) == (2.0, "onions")


def test_blank_lines_are_skipped() -> None:
    lines = parse_ingredient_block("2 eggs\n\n   \n100 ml milk\n")
    assert [i.name for i in lines] == ["eggs", "milk"]


def test_round_trip_as_text() -> None:
    for raw in ["1.5 cup plain flour, sifted", "2 eggs", "salt, to taste", "3 clove garlic"]:
        parsed = parse_ingredient_line(raw)
        assert parsed is not None
        assert parse_ingredient_line(parsed.as_text()) == parsed
