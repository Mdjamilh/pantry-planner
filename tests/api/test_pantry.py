import datetime as dt
import re

from fastapi.testclient import TestClient

from tests.api.conftest import Browser, register
from tests.conftest import TODAY


def item_ids(html: str) -> list[int]:
    return [int(x) for x in re.findall(r'id="item-(\d+)"', html)]


def test_add_item_full_page(user: Browser) -> None:
    r = user.post("/pantry", {"name": "  Basmati   rice ", "quantity": "2", "unit": "kg"})
    assert r.status_code == 303
    page = user.get("/pantry").text
    assert "Basmati rice" in page
    assert "2 kg" in page


def test_add_item_htmx_returns_panel(user: Browser) -> None:
    r = user.post(
        "/pantry",
        {"name": "Milk", "quantity": "1", "unit": "l", "expires_on": TODAY.isoformat()},
        htmx=True,
    )
    assert r.status_code == 200
    assert r.text.lstrip().startswith('<div id="pantry-panel"')
    assert "expires today" in r.text


def test_validation_errors_are_shown(user: Browser) -> None:
    r = user.post("/pantry", {"name": "", "quantity": "-1", "expires_on": "soon"}, htmx=True)
    assert r.status_code == 200
    assert "Give the item a name." in r.text
    assert "Enter an amount above zero." in r.text
    assert "Use a date like" in r.text
    r = user.post("/pantry", {"name": "Eggs", "quantity": "lots"})
    assert r.status_code == 400


def test_sorted_by_expiry_with_undated_last(user: Browser) -> None:
    for name, days in [("Rice", None), ("Yoghurt", 5), ("Spinach", 1)]:
        exp = "" if days is None else (TODAY + dt.timedelta(days=days)).isoformat()
        user.post("/pantry", {"name": name, "quantity": "1", "expires_on": exp})
    page = user.get("/pantry").text
    table = page[page.index("<tbody>") :]
    assert table.index("Spinach") < table.index("Yoghurt") < table.index("Rice")


def test_expired_badge(user: Browser) -> None:
    user.post(
        "/pantry",
        {"name": "Cream", "quantity": "200", "unit": "ml", "expires_on": "2026-10-18"},
    )
    page = user.get("/pantry").text
    assert "expired 3 days ago" in page
    assert "1 expired" in page


def test_edit_and_update_inline(user: Browser) -> None:
    user.post("/pantry", {"name": "Oats", "quantity": "500", "unit": "g"})
    (item_id,) = item_ids(user.get("/pantry").text)
    edit = user.get(f"/pantry/{item_id}/edit", headers={"HX-Request": "true"})
    assert 'name="quantity"' in edit.text
    r = user.post(
        f"/pantry/{item_id}", {"name": "Rolled oats", "quantity": "1.5", "unit": "kg"}, htmx=True
    )
    assert r.status_code == 200
    assert "Rolled oats" in r.text
    assert "1.5 kg" in r.text
    row = user.get(f"/pantry/{item_id}/row", headers={"HX-Request": "true"})
    assert "Rolled oats" in row.text


def test_update_validation_keeps_edit_form(user: Browser) -> None:
    user.post("/pantry", {"name": "Oats", "quantity": "500", "unit": "g"})
    (item_id,) = item_ids(user.get("/pantry").text)
    r = user.post(f"/pantry/{item_id}", {"name": "Oats", "quantity": "0"}, htmx=True)
    assert "Enter an amount above zero." in r.text


def test_delete(user: Browser) -> None:
    user.post("/pantry", {"name": "Tofu", "quantity": "1"})
    (item_id,) = item_ids(user.get("/pantry").text)
    r = user.post(f"/pantry/{item_id}/delete", htmx=True)
    assert r.status_code == 200
    assert r.text == ""
    assert "Tofu" not in user.get("/pantry").text


def test_other_users_items_are_invisible(client: TestClient) -> None:
    alice = Browser(client)
    register(alice, "alice@example.com", "Alice")
    alice.post("/pantry", {"name": "Saffron", "quantity": "1", "unit": "g"})
    (item_id,) = item_ids(alice.get("/pantry").text)
    alice.post("/logout")

    alice.refresh("/register")
    register(alice, "bob@example.com", "Bob")
    bob = alice
    assert "Saffron" not in bob.get("/pantry").text
    assert bob.get(f"/pantry/{item_id}/edit").status_code == 404
    assert bob.post(f"/pantry/{item_id}/delete").status_code == 404
    assert bob.post(f"/pantry/{item_id}", {"name": "Mine", "quantity": "9"}).status_code == 404


def test_edit_without_javascript_renders_full_page(user: Browser) -> None:
    user.post("/pantry", {"name": "Oats", "quantity": "500", "unit": "g"})
    (item_id,) = item_ids(user.get("/pantry").text)
    page = user.get(f"/pantry/{item_id}/edit")
    assert page.text.lstrip().startswith("<!doctype html>")
    assert f'id="e-qty-{item_id}"' in page.text
    assert user.get(f"/pantry/{item_id}/row").status_code == 303
