"""Sign in, sign up, demo login and sign out."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..demo import DEMO_EMAIL, DEMO_PASSWORD, DEMO_USER_ID
from ..deps import DB, AppSettings, MaybeUser
from ..models import User
from ..security import burn_verify, csrf_token, hash_password, verify_csrf, verify_password
from ..web import flash, redirect, render, safe_next

router = APIRouter(dependencies=[Depends(verify_csrf)])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8


def start_session(request: Request, user: User) -> None:
    # A fresh session on login prevents session fixation.
    request.session.clear()
    request.session["uid"] = user.id
    request.session["email"] = user.email
    csrf_token(request)


@router.get("/login")
def login_page(request: Request, user: MaybeUser, next: str = "/") -> Response:
    if user is not None:
        return redirect(safe_next(next))
    return render(request, "auth/login.html", {"next": safe_next(next), "demo_email": DEMO_EMAIL})


@router.post("/login")
def login(
    request: Request,
    db: DB,
    email: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
    next: Annotated[str, Form()] = "/",
) -> Response:
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email)) if email else None
    if user is None:
        burn_verify(password)
    if user is None or not verify_password(user.password_hash, password):
        return render(
            request,
            "auth/login.html",
            {"error": "That email and password don't match.", "email": email, "next": next},
            status_code=400,
        )
    start_session(request, user)
    flash(request, f"Welcome back, {user.display_name}.")
    return redirect(safe_next(next))


@router.post("/demo-login")
def demo_login(request: Request, db: DB, settings: AppSettings) -> Response:
    if not settings.demo_mode:
        return redirect("/login")
    user = db.get(User, DEMO_USER_ID)
    if user is None or not verify_password(user.password_hash, DEMO_PASSWORD):
        flash(request, "The demo account is being reset, try again in a moment.", "error")
        return redirect("/login")
    start_session(request, user)
    flash(request, "You're in the demo kitchen. Changes reset every few hours.")
    return redirect("/")


@router.get("/register")
def register_page(request: Request, user: MaybeUser) -> Response:
    if user is not None:
        return redirect("/")
    return render(request, "auth/register.html", {})


@router.post("/register")
def register(
    request: Request,
    db: DB,
    display_name: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
) -> Response:
    display_name = display_name.strip()
    email = email.strip().lower()
    errors: dict[str, str] = {}
    if not 1 <= len(display_name) <= 80:
        errors["display_name"] = "Tell us what to call you (up to 80 characters)."
    if not EMAIL_RE.match(email) or len(email) > 254:
        errors["email"] = "Enter a valid email address."
    if len(password) < MIN_PASSWORD or len(password) > 256:
        errors["password"] = f"Use at least {MIN_PASSWORD} characters."
    if not errors and db.scalar(select(User.id).where(User.email == email)) is not None:
        errors["email"] = "An account with this email already exists."
    if errors:
        return render(
            request,
            "auth/register.html",
            {"errors": errors, "display_name": display_name, "email": email},
            status_code=400,
        )
    user = User(email=email, display_name=display_name, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return render(
            request,
            "auth/register.html",
            {
                "errors": {"email": "An account with this email already exists."},
                "display_name": display_name,
                "email": email,
            },
            status_code=400,
        )
    start_session(request, user)
    flash(request, "Account created. Start by adding a few things from your fridge.")
    return redirect("/pantry")


@router.post("/logout")
def logout(request: Request) -> Response:
    request.session.clear()
    return redirect("/login")
