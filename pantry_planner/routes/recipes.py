"""Recipe book: list, create, edit, delete and import from pasted text."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import Response

from .. import services
from ..ai.schemas import ImportedRecipe
from ..deps import AI, DB, CurrentUser, Today
from ..models import SLOT_ORDER, Recipe, RecipeIngredient
from ..parsing import IngredientLine, parse_ingredient_block
from ..security import verify_csrf
from ..web import flash, is_htmx, redirect, render

router = APIRouter(prefix="/recipes", dependencies=[Depends(verify_csrf)])

SOURCES = {"manual", "claude", "parser"}
MAX_IMPORT_TEXT = 8000


def _own_recipe(db: DB, user_id: int, recipe_id: int) -> Recipe:
    recipe = services.get_recipe(db, user_id, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


def _ingredients_text(recipe: Recipe) -> str:
    return "\n".join(
        IngredientLine(name=i.name, quantity=i.quantity, unit=i.unit, note=i.note).as_text()
        for i in recipe.ingredients
    )


def _validate(title: str, servings: str, ingredients: str) -> tuple[dict[str, str], int]:
    errors: dict[str, str] = {}
    if not 1 <= len(title.strip()) <= 160:
        errors["title"] = "Give the recipe a title."
    try:
        n = int(servings)
        if not 1 <= n <= 50:
            raise ValueError
    except ValueError:
        errors["servings"] = "Servings should be a number from 1 to 50."
        n = 2
    if not parse_ingredient_block(ingredients):
        errors["ingredients"] = "Add at least one ingredient, one per line."
    return errors, n


def _apply(recipe: Recipe, title: str, servings: int, ingredients: str, instructions: str) -> None:
    recipe.title = " ".join(title.split())
    recipe.servings = servings
    recipe.instructions = instructions.strip()[:10_000]
    recipe.ingredients.clear()
    for pos, line in enumerate(parse_ingredient_block(ingredients)[:60]):
        recipe.ingredients.append(
            RecipeIngredient(
                position=pos,
                name=line.name[:120],
                quantity=line.quantity,
                unit=line.unit[:20],
                note=line.note[:160],
            )
        )


@router.get("")
def recipe_list(request: Request, db: DB, user: CurrentUser, today: Today, q: str = "") -> Response:
    recipes = services.list_recipes(db, user.id, q)
    keys = services.pantry_keys(services.list_pantry(db, user.id), today)
    have = {
        r.id: sum(1 for i in r.ingredients if services.have_ingredient(i.name, keys))
        for r in recipes
    }
    ctx = {"nav": "recipes", "recipes": recipes, "have": have, "q": q}
    if is_htmx(request) and request.headers.get("hx-target") == "recipe-grid":
        return render(request, "partials/recipe_grid.html", ctx)
    return render(request, "recipes/list.html", ctx)


@router.get("/new")
def new_recipe(request: Request, user: CurrentUser) -> Response:
    return render(
        request,
        "recipes/form.html",
        {"nav": "recipes", "form": {"servings": "2", "source": "manual"}, "action": "/recipes"},
    )


@router.post("")
def create_recipe(
    request: Request,
    db: DB,
    user: CurrentUser,
    title: Annotated[str, Form()] = "",
    servings: Annotated[str, Form()] = "2",
    ingredients: Annotated[str, Form()] = "",
    instructions: Annotated[str, Form()] = "",
    source: Annotated[str, Form()] = "manual",
) -> Response:
    errors, n = _validate(title, servings, ingredients)
    if errors:
        form = {
            "title": title,
            "servings": servings,
            "ingredients": ingredients,
            "instructions": instructions,
            "source": source,
        }
        return render(
            request,
            "recipes/form.html",
            {"nav": "recipes", "form": form, "errors": errors, "action": "/recipes"},
            status_code=400,
        )
    recipe = Recipe(user_id=user.id, source=source if source in SOURCES else "manual")
    _apply(recipe, title, n, ingredients, instructions)
    db.add(recipe)
    db.commit()
    flash(request, f"Saved {recipe.title}.")
    return redirect(f"/recipes/{recipe.id}")


@router.get("/import")
def import_page(request: Request, user: CurrentUser) -> Response:
    return render(request, "recipes/import.html", {"nav": "recipes"})


@router.post("/import/preview")
def import_preview(
    request: Request,
    user: CurrentUser,
    assistant: AI,
    text: Annotated[str, Form()] = "",
) -> Response:
    text = text.strip()
    if not text:
        template = "partials/import_preview.html" if is_htmx(request) else "recipes/import.html"
        return render(
            request,
            template,
            {"nav": "recipes", "error": "Paste a recipe first."},
            status_code=200 if is_htmx(request) else 400,
        )
    limiter = request.app.state.ai_limiter
    if assistant.settings.ai_enabled and not limiter.allow(f"import:{user.id}"):
        result = None
        error = "You've imported a lot of recipes just now. Try again in a few minutes."
    else:
        result = assistant.import_recipe(text[:MAX_IMPORT_TEXT])
        error = None
    ctx: dict[str, object] = {"nav": "recipes", "text": text, "error": error}
    if result is not None:
        ctx.update(result=result, form=_form_from_import(result.recipe, result.provider))
    template = "partials/import_preview.html" if is_htmx(request) else "recipes/import.html"
    return render(request, template, ctx)


def _form_from_import(recipe: ImportedRecipe, provider: str) -> dict[str, str]:
    lines = [
        IngredientLine(name=i.name, quantity=i.quantity, unit=i.unit, note=i.note).as_text()
        for i in recipe.ingredients
    ]
    return {
        "title": recipe.title,
        "servings": str(recipe.servings),
        "ingredients": "\n".join(lines),
        "instructions": "\n".join(recipe.steps),
        "source": "claude" if provider == "claude" else "parser",
    }


@router.get("/{recipe_id}")
def recipe_detail(
    request: Request, recipe_id: int, db: DB, user: CurrentUser, today: Today
) -> Response:
    recipe = _own_recipe(db, user.id, recipe_id)
    keys = services.pantry_keys(services.list_pantry(db, user.id), today)
    monday = services.week_start(today)
    days = [monday + dt.timedelta(days=i) for i in range(7)]
    return render(
        request,
        "recipes/detail.html",
        {
            "nav": "recipes",
            "recipe": recipe,
            "have": {i.id: services.have_ingredient(i.name, keys) for i in recipe.ingredients},
            "steps": [s for s in recipe.instructions.splitlines() if s.strip()],
            "days": days,
            "today": today,
            "slots": [s.value for s in SLOT_ORDER],
        },
    )


@router.get("/{recipe_id}/edit")
def edit_recipe(request: Request, recipe_id: int, db: DB, user: CurrentUser) -> Response:
    recipe = _own_recipe(db, user.id, recipe_id)
    form = {
        "title": recipe.title,
        "servings": str(recipe.servings),
        "ingredients": _ingredients_text(recipe),
        "instructions": recipe.instructions,
        "source": recipe.source,
    }
    return render(
        request,
        "recipes/form.html",
        {"nav": "recipes", "form": form, "recipe": recipe, "action": f"/recipes/{recipe.id}"},
    )


@router.post("/{recipe_id}")
def update_recipe(
    request: Request,
    recipe_id: int,
    db: DB,
    user: CurrentUser,
    title: Annotated[str, Form()] = "",
    servings: Annotated[str, Form()] = "2",
    ingredients: Annotated[str, Form()] = "",
    instructions: Annotated[str, Form()] = "",
) -> Response:
    recipe = _own_recipe(db, user.id, recipe_id)
    errors, n = _validate(title, servings, ingredients)
    if errors:
        form = {
            "title": title,
            "servings": servings,
            "ingredients": ingredients,
            "instructions": instructions,
            "source": recipe.source,
        }
        return render(
            request,
            "recipes/form.html",
            {
                "nav": "recipes",
                "form": form,
                "errors": errors,
                "recipe": recipe,
                "action": f"/recipes/{recipe.id}",
            },
            status_code=400,
        )
    _apply(recipe, title, n, ingredients, instructions)
    db.commit()
    flash(request, "Recipe updated.")
    return redirect(f"/recipes/{recipe.id}")


@router.post("/{recipe_id}/delete")
def delete_recipe(request: Request, recipe_id: int, db: DB, user: CurrentUser) -> Response:
    recipe = _own_recipe(db, user.id, recipe_id)
    title = recipe.title
    db.delete(recipe)
    db.commit()
    flash(request, f"Deleted {title}.")
    return redirect("/recipes")
