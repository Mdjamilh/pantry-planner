"""Template setup and small helpers for rendering pages and htmx partials."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from . import __version__, units
from .security import csrf_token

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _static(path: str) -> str:
    return f"/static/{path}?v={__version__}"


def _days_label(days: int | None) -> str:
    if days is None:
        return "no date"
    if days < -1:
        return f"expired {-days} days ago"
    if days == -1:
        return "expired yesterday"
    if days == 0:
        return "expires today"
    if days == 1:
        return "expires tomorrow"
    return f"{days} days left"


def _days_tone(days: int | None, soon: int = 3) -> str:
    if days is None:
        return "none"
    if days < 0:
        return "expired"
    if days <= soon:
        return "soon"
    return "ok"


def _short_date(d: dt.date) -> str:
    return f"{d:%a} {d.day} {d:%b}"


templates.env.globals.update(
    static=_static,
    csrf_token=csrf_token,
    format_amount=units.format_amount,
    format_quantity=units.format_quantity,
    days_label=_days_label,
    days_tone=_days_tone,
    short_date=_short_date,
    version=__version__,
)


def is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request") == "true"


def flash(request: Request, message: str, kind: str = "ok") -> None:
    messages = request.session.get("flash", [])
    messages.append({"kind": kind, "text": message})
    request.session["flash"] = messages[-3:]


def render(
    request: Request,
    name: str,
    context: dict[str, Any] | None = None,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> HTMLResponse:
    settings = request.app.state.settings
    ctx: dict[str, Any] = {
        "user": getattr(request.state, "user", None),
        "demo_mode": settings.demo_mode,
        "ai_enabled": settings.ai_enabled,
        "ai_model": settings.anthropic_model,
        "nav": "",
    }
    if not is_htmx(request):
        ctx["flashes"] = request.session.pop("flash", [])
    ctx.update(context or {})
    response: HTMLResponse = templates.TemplateResponse(
        request, name, ctx, status_code=status_code, headers=headers
    )
    return response


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def htmx_redirect(url: str) -> Response:
    return Response(status_code=204, headers={"HX-Redirect": url})


def safe_next(target: str | None, default: str = "/") -> str:
    """Only allow same-site relative redirects after login."""
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return default
    return target
