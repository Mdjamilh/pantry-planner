"""FastAPI dependencies: database session, clock, current user."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .ai.service import Assistant
from .config import Settings
from .models import User


class LoginRequired(Exception):
    """Raised when a page needs a signed-in user; handled in main.py."""


def get_db(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session()


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_today(request: Request) -> dt.date:
    today: dt.date = request.app.state.clock()
    return today


def get_assistant(request: Request) -> Assistant:
    assistant: Assistant = request.app.state.assistant
    return assistant


def optional_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User | None:
    uid = request.session.get("uid")
    email = request.session.get("email")
    if not isinstance(uid, int) or not isinstance(email, str):
        return None
    user = db.get(User, uid)
    # The email check guards against ids being reused after a demo reset.
    if user is None or user.email != email:
        request.session.pop("uid", None)
        request.session.pop("email", None)
        return None
    request.state.user = user
    return user


def current_user(user: Annotated[User | None, Depends(optional_user)]) -> User:
    if user is None:
        raise LoginRequired
    return user


DB = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]
MaybeUser = Annotated[User | None, Depends(optional_user)]
Today = Annotated[dt.date, Depends(get_today)]
AppSettings = Annotated[Settings, Depends(get_settings)]
AI = Annotated[Assistant, Depends(get_assistant)]
