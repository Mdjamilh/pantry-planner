"""Password hashing (Argon2id) and CSRF protection.

CSRF uses the synchroniser-token pattern: a random token lives in the signed
session cookie and every unsafe request must echo it back, either as a hidden
`csrf_token` form field or as an `X-CSRF-Token` header (htmx sends the header
for every request, see base.html).
"""

from __future__ import annotations

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, Request

_hasher = PasswordHasher()

CSRF_SESSION_KEY = "csrf"
CSRF_FORM_FIELD = "csrf_token"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# A real hash to compare against when the email is unknown, so failed logins
# take about the same time whether or not the account exists.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def burn_verify(password: str) -> None:
    verify_password(_DUMMY_HASH, password)


def csrf_token(request: Request) -> str:
    token = request.session.get(CSRF_SESSION_KEY)
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token
    return token


async def verify_csrf(request: Request) -> None:
    """FastAPI dependency: reject unsafe requests without a valid token."""
    if request.method in SAFE_METHODS:
        return
    expected = request.session.get(CSRF_SESSION_KEY)
    sent = request.headers.get(CSRF_HEADER)
    if not sent:
        content_type = request.headers.get("content-type", "")
        if content_type.startswith(("application/x-www-form-urlencoded", "multipart/form-data")):
            form = await request.form()
            value = form.get(CSRF_FORM_FIELD)
            sent = value if isinstance(value, str) else None
    if not expected or not sent or not secrets.compare_digest(str(expected), sent):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
