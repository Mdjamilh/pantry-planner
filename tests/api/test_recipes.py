from fastapi.testclient import TestClient

from tests.api.conftest import Browser, add_recipe, register

SOUP = """1 onion, chopped
2 cloves garlic
400 g chopped tomatoes
500 ml vegetable stock
salt to taste"""


def test_create_and_view(user: Browser) -> None:
    rid = add_recipe(user, "Tomato soup", 4, SOUP)
    page = user.get(f"/recipes/{rid}").text
    assert "Tomato soup" in page
    assert "400 g" in page
    assert "(chopped)" in page
    assert "to buy" in page
    assert "Serves 4" in page


def test_pantry_matching_on_detail_page(user: Browser) -> None:
    user.post("/pantry", {"name": "Red onions", "quantity": "3"})
    rid = add_recipe(user, "Tomato soup", 4, SOUP)
    page = user.get(f"/recipes/{rid}").text
    assert "You have 1 of 5 ingredients" in page


def test_validation(user: Browser) -> None:
    r = user.post("/recipes", {"title": "", "servings": "0", "ingredients": "   "})
    assert r.status_code == 400
    assert "Give the recipe a title." in r.text
    assert "Servings should be" in r.text
    assert "at least one ingredient" in r.text


def test_edit_round_trips_ingredients(user: Browser) -> None:
    rid = add_recipe(user, "Soup", 2, SOUP)
    form = user.get(f"/recipes/{rid}/edit").text
    assert "400 g chopped tomatoes" in form
    assert "1 onion, chopped" in form
    r = user.post(
        f"/recipes/{rid}",
        {"title": "Better soup", "servings": "3", "ingredients": "1 kg tomatoes", "instructions": ""},
    )
    assert r.status_code == 303
    page = user.get(f"/recipes/{rid}").text
    assert "Better soup" in page
    assert "1 kg" in page
    assert "onion" not in page


def test_list_and_search(user: Browser) -> None:
    add_recipe(user, "Lentil curry", 4, "200 g red lentils")
    add_recipe(user, "Pancakes", 2, "2 eggs")
    page = user.get("/recipes").text
    assert "Lentil curry" in page and "Pancakes" in page
    r = user.get("/recipes?q=lent", headers={"HX-Request": "true", "HX-Target": "recipe-grid"})
    assert r.text.lstrip().startswith('<div id="recipe-grid"')
    assert "Lentil curry" in r.text
    assert "Pancakes" not in r.text


def test_delete(user: Browser) -> None:
    rid = add_recipe(user, "Toast", 1, "2 slices bread")
    r = user.post(f"/recipes/{rid}/delete")
    assert r.status_code == 303
    assert user.get(f"/recipes/{rid}").status_code == 404


def test_import_preview_with_parser(user: Browser) -> None:
    text = "Quick omelette\nServes 1\nIngredients\n3 eggs\n30 g cheddar, grated\nMethod\nWhisk and cook."
    r = user.post("/recipes/import/preview", {"text": text}, htmx=True)
    assert r.status_code == 200
    assert 'data-provider="fallback"' in r.text
    assert "Read by the built-in parser" in r.text
    assert "30 g cheddar, grated" in r.text
    assert 'name="source" value="parser"' in r.text


def test_import_full_page_and_save(user: Browser) -> None:
    r = user.post("/recipes/import/preview", {"text": "Toast\n2 slices bread\n1 tbsp butter"})
    assert r.status_code == 200
    assert "Import a recipe" in r.text
    r = user.post(
        "/recipes",
        {"title": "Toast", "servings": "1", "ingredients": "2 slices bread", "source": "parser"},
    )
    rid = int(r.headers["location"].rsplit("/", 1)[1])
    assert "imported with the built-in parser" in user.get(f"/recipes/{rid}").text


def test_import_requires_text(user: Browser) -> None:
    r = user.post("/recipes/import/preview", {"text": "  "}, htmx=True)
    assert "Paste a recipe first." in r.text


def test_unknown_source_is_stored_as_manual(user: Browser) -> None:
    r = user.post(
        "/recipes", {"title": "X", "servings": "1", "ingredients": "1 egg", "source": "hacker"}
    )
    rid = int(r.headers["location"].rsplit("/", 1)[1])
    page = user.get(f"/recipes/{rid}").text
    assert "imported" not in page


def test_recipes_are_private(client: TestClient) -> None:
    b = Browser(client)
    register(b, "a@example.com", "A")
    rid = add_recipe(b, "Secret sauce", 2, "1 tbsp miso")
    b.post("/logout")
    b.refresh("/register")
    register(b, "b@example.com", "B")
    assert b.get(f"/recipes/{rid}").status_code == 404
    assert b.get(f"/recipes/{rid}/edit").status_code == 404
    assert b.post(f"/recipes/{rid}/delete").status_code == 404
    assert "Secret sauce" not in b.get("/recipes").text
