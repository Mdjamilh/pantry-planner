"""Application factory."""

from __future__ import annotations

import datetime as dt
import logging
import threading
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import __version__
from .ai.service import Assistant
from .config import Settings, get_settings
from .db import Database
from .demo import DemoResetter
from .deps import LoginRequired
from .migrate import upgrade_to_head
from .services import RateLimiter
from .web import STATIC_DIR, htmx_redirect, is_htmx, redirect, render

log = logging.getLogger(__name__)

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; "
    "base-uri 'self'; object-src 'none'"
)


def create_app(
    settings: Settings | None = None,
    *,
    assistant: Assistant | None = None,
    clock: Callable[[], dt.date] = dt.date.today,
) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Pantry Planner",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.db = Database(settings.database_url)
    app.state.assistant = assistant or Assistant(settings)
    app.state.clock = clock
    app.state.ai_limiter = RateLimiter(limit=12, window_seconds=600)
    app.state.demo = DemoResetter(settings.demo_reset_hours) if settings.demo_mode else None
    demo_lock = threading.Lock()

    if settings.auto_migrate:
        upgrade_to_head(app.state.db.engine)

    def maybe_reset_demo() -> None:
        resetter: DemoResetter | None = app.state.demo
        if resetter is None or not resetter.due():
            return
        with demo_lock:
            if not resetter.due():
                return
            with app.state.db.sessionmaker() as session:
                resetter.reset(session, clock())
            log.info("demo data reset")

    maybe_reset_demo()

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not request.url.path.startswith("/static/"):
            maybe_reset_demo()
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        if settings.secure_cookies:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        if request.url.path.startswith("/static/"):
            response.headers.setdefault("Cache-Control", "public, max-age=604800")
        elif "text/html" in response.headers.get("content-type", ""):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="pp_session",
        max_age=14 * 24 * 3600,
        same_site="lax",
        https_only=bool(settings.secure_cookies),
    )

    @app.exception_handler(LoginRequired)
    async def _login_required(request: Request, _exc: LoginRequired) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Not signed in"}, status_code=401)
        target = "/login"
        if request.method == "GET" and request.url.path != "/":
            target += f"?next={request.url.path}"
        if is_htmx(request):
            return htmx_redirect(target)
        return redirect(target)

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException) -> Response:
        if request.url.path.startswith("/api/") or is_htmx(request):
            return JSONResponse(
                {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
            )
        return render(
            request,
            "error.html",
            {"status": exc.status_code, "detail": exc.detail},
            status_code=exc.status_code,
        )

    from .routes import api, auth, cook, pages, pantry, plan, recipes, shopping

    for module in (auth, pages, pantry, recipes, plan, shopping, cook, api):
        app.include_router(module.router)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
