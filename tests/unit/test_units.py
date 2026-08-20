import pytest

from pantry_planner import units


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Tablespoons", "tbsp"),
        ("tbsp.", "tbsp"),
        ("grams", "g"),
        ("KG", "kg"),
        ("", "pc"),
        ("each", "pc"),
        ("cloves", "clove"),
        ("fluid  ounces", "fl oz"),
        ("smidgen", "smidgen"),
    ],
)
def test_normalize_unit(raw: str, expected: str) -> None:
    assert units.normalize_unit(raw) == expected


def test_to_base_mass_and_volume() -> None:
    assert units.to_base(1.5, "kg") == ("mass", 1500.0)
    dim, ml = units.to_base(2, "tbsp")
    assert dim == "volume"
    assert ml == pytest.approx(29.57, rel=1e-3)


def test_unknown_units_get_their_own_dimension() -> None:
    assert units.to_base(2, "cloves") == ("unit:clove", 2)
    assert units.dimension_of("can") == "unit:can"


def test_convert_same_dimension() -> None:
    assert units.convert(1, "lb", "g") == pytest.approx(453.59, rel=1e-4)
    assert units.convert(3, "tsp", "tbsp") == pytest.approx(1.0)


def test_convert_across_dimensions_is_none() -> None:
    assert units.convert(1, "kg", "ml") is None
    assert units.convert(1, "clove", "g") is None


@pytest.mark.parametrize(
    ("dim", "base", "expected"),
    [
        ("mass", 1500, (1.5, "kg")),
        ("mass", 250, (250, "g")),
        ("volume", 2365.88, (2.37, "l")),
        ("volume", 14.79, (14.8, "ml")),
        ("count", 3, (3, "pc")),
        ("unit:clove", 2, (2, "clove")),
    ],
)
def test_humanize(dim: str, base: float, expected: tuple[float, str]) -> None:
    assert units.humanize(dim, base) == expected


def test_format_amount() -> None:
    assert units.format_amount(2.0, "pc") == "2"
    assert units.format_amount(0.5, "cups") == "0.5 cup"
    assert units.format_amount(None, "") == ""


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("Tomatoes", "tomato"),
        ("2 large ripe tomatoes", "tomato"),
        ("Eggs", "egg"),
        ("Cherries", "cherry"),
        ("Red onions, finely chopped", "red onion"),
        ("Spinach leaves", "spinach leaf"),
        ("Rice", "rice"),
        ("Chickpeas", "chickpeas"),
        ("Bell pepper (red)", "bell pepper"),
        ("Peaches", "peach"),
        ("Glass", "glass"),
    ],
)
def test_normalize_name(name: str, key: str) -> None:
    assert units.normalize_name(name) == key
