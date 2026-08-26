import datetime as dt

import pytest

from pantry_planner.shopping import Need, Stock, build_shopping_list, scale_quantity

TODAY = dt.date(2026, 10, 20)


def names(items):  # type: ignore[no-untyped-def]
    return [(i.key, i.amount_text) for i in items]


def test_needs_are_summed_across_recipes() -> None:
    needs = [
        Need("Onion", 1, "", "Soup"),
        Need("onions", 2, "pc", "Curry"),
    ]
    items = build_shopping_list(needs, [], TODAY)
    assert names(items) == [("onion", "3")]
    assert items[0].recipes == ["Soup", "Curry"]


def test_pantry_is_subtracted_unit_aware() -> None:
    needs = [Need("Flour", 750, "g", "Bread")]
    stock = [Stock("flour", 0.5, "kg")]
    items = build_shopping_list(needs, stock, TODAY)
    assert names(items) == [("flour", "250 g")]
    assert items[0].note == "you have 500 g"


def test_fully_covered_items_are_dropped() -> None:
    needs = [Need("Milk", 250, "ml", "Pancakes")]
    stock = [Stock("Milk", 1, "l")]
    assert build_shopping_list(needs, stock, TODAY) == []


def test_volume_units_combine() -> None:
    needs = [Need("Olive oil", 2, "tbsp", "A"), Need("olive oil", 1, "cup", "B")]
    items = build_shopping_list(needs, [], TODAY)
    assert items[0].quantity == pytest.approx(266, abs=1)
    assert items[0].unit == "ml"


def test_expired_stock_does_not_count() -> None:
    needs = [Need("Spinach", 200, "g", "Salad")]
    stock = [Stock("spinach", 300, "g", expires_on=TODAY - dt.timedelta(days=1))]
    assert names(build_shopping_list(needs, stock, TODAY)) == [("spinach", "200 g")]


def test_stock_expiring_today_still_counts() -> None:
    needs = [Need("Spinach", 200, "g", "Salad")]
    stock = [Stock("spinach", 300, "g", expires_on=TODAY)]
    assert build_shopping_list(needs, stock, TODAY) == []


def test_mismatched_dimensions_are_flagged() -> None:
    needs = [Need("Garlic", 3, "cloves", "Pasta")]
    stock = [Stock("garlic", 1, "head")]
    items = build_shopping_list(needs, stock, TODAY)
    assert names(items) == [("garlic", "3 clove")]
    assert "units don't compare" in items[0].note


def test_unquantified_items_listed_only_when_missing() -> None:
    needs = [Need("Salt", None, "", "Soup"), Need("Pepper", None, "", "Soup")]
    stock = [Stock("salt", 1, "kg")]
    items = build_shopping_list(needs, stock, TODAY)
    assert [(i.key, i.quantity, i.note) for i in items] == [
        ("pepper", None, "amount not specified")
    ]


def test_large_amounts_are_humanised() -> None:
    needs = [Need("Potatoes", 800, "g", "A"), Need("potato", 0.7, "kg", "B")]
    assert names(build_shopping_list(needs, [], TODAY)) == [("potato", "1.5 kg")]


@pytest.mark.parametrize(
    ("qty", "recipe", "planned", "expected"),
    [(200, 4, 2, 100), (1, 2, 3, 1.5), (None, 2, 4, None), (5, 0, 2, 5)],
)
def test_scale_quantity(qty, recipe, planned, expected) -> None:  # type: ignore[no-untyped-def]
    assert scale_quantity(qty, recipe, planned) == expected
