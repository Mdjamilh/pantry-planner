"""End-to-end flows in a real browser (Chromium via Playwright)."""

from __future__ import annotations

import re
import uuid

from playwright.sync_api import Page, expect


def demo_login(page: Page, base: str) -> None:
    page.goto(base + "/login")
    page.get_by_role("button", name="Try the demo").click()
    expect(page.get_by_role("heading", name="Hello, Demo Cook")).to_be_visible()


def test_demo_login_and_add_pantry_item(page: Page, server_url: str) -> None:
    demo_login(page, server_url)
    expect(page.get_by_role("note")).to_contain_text("resets every few hours")

    page.get_by_role("link", name="Pantry", exact=True).click()
    name = f"Cherry tomatoes {uuid.uuid4().hex[:6]}"
    page.get_by_label("Item").fill(name)
    page.get_by_label("Amount").fill("250")
    page.get_by_label("Unit").select_option("g")
    page.get_by_role("button", name="Add", exact=True).click()

    row = page.locator("tr", has_text=name)
    expect(row).to_be_visible()
    expect(row).to_contain_text("250 g")
    # htmx swapped the panel in place: still on /pantry, no full reload.
    expect(page).to_have_url(re.compile(r"/pantry$"))

    page.once("dialog", lambda d: d.accept())
    row.get_by_role("button", name=f"Remove {name}").click()
    expect(page.locator("tr", has_text=name)).to_have_count(0)


def test_plan_a_meal_and_buy_it(page: Page, server_url: str) -> None:
    demo_login(page, server_url)
    page.goto(server_url + "/plan")
    cell = page.locator(".plan-day").first.locator(".plan-cell").first  # Monday breakfast
    cell.locator("select").select_option(label="Greek yoghurt breakfast bowl")
    cell.get_by_role("button", name=re.compile("^Add to")).click()
    expect(page.locator(".plan-day").first.locator(".plan-cell").first).to_contain_text(
        "Greek yoghurt breakfast bowl"
    )

    page.get_by_role("link", name="Shopping list").click()
    expect(page.get_by_role("heading", level=1)).to_contain_text("For Mon")
    first = page.locator(".shopping li").first
    item = first.locator("strong").evaluate("el => el.firstChild.textContent.trim()")
    first.get_by_role("button", name=f"Bought {item}").click()
    expect(page.locator("#shopping-list .alert")).to_have_text(f"Moved {item} into the pantry.")
    expect(
        page.locator(".shopping li strong", has_text=re.compile(f"^{re.escape(item)}"))
    ).to_have_count(0)


def test_what_can_i_cook_shows_who_answered(page: Page, server_url: str) -> None:
    demo_login(page, server_url)
    page.get_by_role("link", name="What can I cook?").click()
    page.get_by_role("button", name="Suggest dishes").click()
    provider = page.locator(".provider")
    expect(provider).to_be_visible()
    expect(provider).to_contain_text(re.compile("Answered by (Claude|the built-in matcher)"))
    expect(page.locator("article.suggestion").first).to_be_visible()


def test_register_and_import_a_recipe(page: Page, server_url: str) -> None:
    page.goto(server_url + "/register")
    page.get_by_label("Your name").fill("E2E Cook")
    page.get_by_label("Email").fill(f"e2e-{uuid.uuid4().hex[:8]}@example.com")
    page.get_by_label("Password").fill("a-long-password")
    page.get_by_role("button", name="Create account").click()
    expect(page).to_have_url(re.compile(r"/pantry$"))

    page.goto(server_url + "/recipes/import")
    page.get_by_label("Recipe text").fill(
        "Lemon rice\nServes 2\nIngredients\n150 g rice\n1 lemon, zested\n"
        "Method\nCook the rice.\nStir in the lemon."
    )
    page.get_by_role("button", name="Read recipe").click()
    expect(page.locator("#import-preview .provider")).to_be_visible()
    expect(page.get_by_label("Title")).to_have_value("Lemon rice")
    expect(page.get_by_label("Ingredients")).to_have_value(re.compile("150 g rice"))
    page.get_by_role("button", name="Save recipe").click()
    expect(page.get_by_role("heading", level=1)).to_have_text("Lemon rice")
    expect(page.locator(".ingredients")).to_contain_text("150 g")


def test_theme_toggle_persists(page: Page, server_url: str) -> None:
    page.goto(server_url + "/login")
    page.get_by_role("button", name="Toggle dark mode").click()
    theme = page.evaluate("document.documentElement.dataset.theme")
    page.reload()
    assert page.evaluate("document.documentElement.dataset.theme") == theme
