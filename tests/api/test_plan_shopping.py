import re

from fastapi.testclient import TestClient

from tests.api.conftest import Browser, add_recipe, register

MONDAY = "2026-10-19"
WEDNESDAY = "2026-10-21"


def plan(
    user: Browser,
    rid: int,
    day: str = WEDNESDAY,
    slot: str = "dinner",
    servings: str = "",
    htmx: bool = False,
):  # type: ignore[no-untyped-def]
    return user.post(
        "/plan", {"day": day, "slot": slot, "recipe_id": str(rid), "servings": servings}, htmx=htmx
    )


def test_plan_page_shows_week_and_today(user: Browser) -> None:
    page = user.get("/plan").text
    assert "This week" in page
    assert "Mon 19 Oct - Sun 25 Oct" in page
    assert page.count('class="plan-day ') == 7
    assert "is-today" in page


def test_week_navigation(user: Browser) -> None:
    page = user.get("/plan?week=2026-10-29").text
    assert "Week of Mon 26 Oct" in page
    assert "/plan?week=2026-10-19" in page
    assert "/plan?week=2026-11-02" in page
    assert "This week" in user.get("/plan?week=garbage").text


def test_add_and_remove_entry_with_htmx(user: Browser) -> None:
    rid = add_recipe(user, "Pasta", 2, "200 g pasta")
    r = plan(user, rid, htmx=True)
    assert r.status_code == 200
    assert r.text.lstrip().startswith('<div class="plan-cell" id="cell-2026-10-21-dinner"')
    assert "Pasta" in r.text and "x2" in r.text
    entry_id = int(re.search(r"/plan/(\d+)/delete", r.text).group(1))  # type: ignore[union-attr]
    r = user.post(f"/plan/{entry_id}/delete", htmx=True)
    assert "Pasta</a>" not in r.text


def test_adding_twice_updates_servings(user: Browser) -> None:
    rid = add_recipe(user, "Pasta", 2, "200 g pasta")
    plan(user, rid, servings="2")
    r = plan(user, rid, servings="6", htmx=True)
    assert r.text.count("Pasta</a>") == 1
    assert "x6" in r.text


def test_rejects_bad_input(user: Browser) -> None:
    rid = add_recipe(user, "Pasta", 2, "200 g pasta")
    assert plan(user, rid, day="tomorrow").status_code == 400
    assert plan(user, rid, slot="brunch").status_code == 400
    assert plan(user, 9999).status_code == 404


def test_shopping_list_scales_and_subtracts(user: Browser) -> None:
    rid = add_recipe(user, "Pasta", 2, "200 g pasta\n1 tbsp olive oil\n2 cloves garlic")
    plan(user, rid, day=MONDAY, servings="4")  # double the recipe
    plan(user, rid, day=WEDNESDAY, servings="2")
    user.post("/pantry", {"name": "Pasta", "quantity": "0.5", "unit": "kg"})
    user.post("/pantry", {"name": "Olive oil", "quantity": "1", "unit": "l"})

    page = user.get("/shopping").text
    # 600 g pasta needed, 500 g in the pantry.
    assert "100 g" in page
    assert "you have 500 g" in page
    # Oil is fully covered; garlic is needed: 6 cloves.
    assert "Olive oil" not in page.split('id="shopping-list"')[1]
    assert "6 clove" in page


def test_api_shopping_list(user: Browser) -> None:
    rid = add_recipe(user, "Soup", 4, "1 kg carrots\n2 onions")
    plan(user, rid, servings="2")
    data = user.get("/api/shopping-list").json()
    assert data["week_start"] == MONDAY
    assert {(i["name"], i["quantity"], i["unit"]) for i in data["items"]} == {
        ("carrots", 500, "g"),
        ("onions", 1, "pc"),
    }


def test_bought_moves_item_to_pantry(user: Browser) -> None:
    rid = add_recipe(user, "Omelette", 1, "3 eggs")
    plan(user, rid)
    r = user.post(
        "/shopping/bought",
        {"name": "eggs", "quantity": "3", "unit": "pc", "week": MONDAY},
        htmx=True,
    )
    assert r.status_code == 200
    assert "Moved eggs into the pantry." in r.text
    assert "You have everything" in r.text
    pantry = user.get("/api/pantry").json()["items"]
    assert [(i["name"], i["quantity"]) for i in pantry] == [("eggs", 3)]


def test_empty_states(user: Browser) -> None:
    assert "Nothing planned this week" in user.get("/shopping").text


def test_plan_is_private(client: TestClient) -> None:
    b = Browser(client)
    register(b, "a@example.com", "A")
    rid = add_recipe(b, "Mine", 2, "1 egg")
    r = plan(b, rid, htmx=True)
    entry_id = int(re.search(r"/plan/(\d+)/delete", r.text).group(1))  # type: ignore[union-attr]
    b.post("/logout")
    b.refresh("/register")
    register(b, "b@example.com", "B")
    assert b.post(f"/plan/{entry_id}/delete").status_code == 404
    assert plan(b, rid).status_code == 404
    assert b.get("/api/shopping-list").json()["items"] == []
