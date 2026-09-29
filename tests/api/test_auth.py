from fastapi import FastAPI
from fastapi.testclient import TestClient

from pantry_planner.demo import DEMO_EMAIL, DEMO_PASSWORD
from tests.api.conftest import AppFactory, Browser, register


def test_pages_require_login(client: TestClient) -> None:
    for path in ["/", "/pantry", "/recipes", "/plan", "/shopping", "/cook"]:
        r = client.get(path)
        assert r.status_code == 303
        assert r.headers["location"].startswith("/login")


def test_login_redirect_keeps_next(client: TestClient) -> None:
    r = client.get("/pantry")
    assert r.headers["location"] == "/login?next=/pantry"


def test_htmx_requests_get_hx_redirect(client: TestClient) -> None:
    r = client.get("/pantry", headers={"HX-Request": "true"})
    assert r.status_code == 204
    assert r.headers["hx-redirect"].startswith("/login")


def test_api_returns_401_json(client: TestClient) -> None:
    r = client.get("/api/pantry")
    assert r.status_code == 401
    assert r.json() == {"detail": "Not signed in"}


def test_register_login_logout(client: TestClient) -> None:
    b = Browser(client)
    register(b)
    assert "Hello, Sam" in client.get("/").text

    r = b.post("/logout")
    assert r.status_code == 303
    assert client.get("/").status_code == 303

    b.refresh("/login")
    r = b.post("/login", {"email": "COOK@example.com ", "password": "long-enough-pw"})
    assert r.status_code == 303
    assert client.get("/").status_code == 200


def test_wrong_password_is_rejected(user: Browser) -> None:
    user.post("/logout")
    user.refresh("/login")
    r = user.post("/login", {"email": "cook@example.com", "password": "nope-nope"})
    assert r.status_code == 400
    assert "don&#39;t match" in r.text


def test_register_validation(client: TestClient) -> None:
    b = Browser(client)
    r = b.post("/register", {"display_name": "", "email": "bad", "password": "short"})
    assert r.status_code == 400
    assert "valid email" in r.text
    assert "at least 8" in r.text


def test_duplicate_email(client: TestClient) -> None:
    b = Browser(client)
    register(b)
    b.post("/logout")
    b.refresh("/register")
    r = b.post(
        "/register",
        {"display_name": "Again", "email": "cook@example.com", "password": "long-enough-pw"},
    )
    assert r.status_code == 400
    assert "already exists" in r.text


def test_passwords_are_hashed(app: FastAPI, user: Browser) -> None:
    from sqlalchemy import select

    from pantry_planner.models import User

    with app.state.db.sessionmaker() as s:
        stored = s.scalars(select(User.password_hash)).one()
    assert stored.startswith("$argon2id$")
    assert "long-enough-pw" not in stored


def test_open_redirect_is_blocked(client: TestClient) -> None:
    b = Browser(client)
    register(b)
    b.post("/logout")
    b.refresh("/login")
    r = b.post(
        "/login",
        {"email": "cook@example.com", "password": "long-enough-pw", "next": "//evil.example"},
    )
    assert r.headers["location"] == "/"


def test_csrf_is_required(client: TestClient) -> None:
    client.get("/login")
    r = client.post("/login", data={"email": "a@b.co", "password": "x"})
    assert r.status_code == 403
    r = client.post("/login", data={"email": "a@b.co", "password": "x", "csrf_token": "forged"})
    assert r.status_code == 403


def test_csrf_header_works_for_htmx(client: TestClient) -> None:
    b = Browser(client)
    register(b)
    r = client.post(
        "/pantry",
        data={"name": "Rice", "quantity": "1", "unit": "kg"},
        headers={"HX-Request": "true", "X-CSRF-Token": b.token},
    )
    assert r.status_code == 200
    assert "Rice" in r.text


def test_demo_login_only_in_demo_mode(client: TestClient) -> None:
    b = Browser(client)
    r = b.post("/demo-login")
    assert r.headers["location"] == "/login"
    assert "Try the demo" not in client.get("/login").text


def test_demo_login(make_app: AppFactory) -> None:
    app = make_app(demo_mode=True)
    with TestClient(app, follow_redirects=False) as client:
        page = client.get("/login").text
        assert "Try the demo" in page
        assert "resets every few hours" in page
        b = Browser(client)
        r = b.post("/demo-login")
        assert r.status_code == 303
        home = client.get("/")
        assert "Hello, Demo Cook" in home.text
        b.refresh()  # the token rotates on login

        # The demo account also works with its password.
        b.post("/logout")
        b.refresh("/login")
        r = b.post("/login", {"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert r.status_code == 303


def test_session_cookie_flags(make_app: AppFactory) -> None:
    app = make_app(secure_cookies=True)
    with TestClient(app, base_url="https://testserver", follow_redirects=False) as client:
        r = client.get("/login")
        cookie = r.headers["set-cookie"].lower()
        assert "httponly" in cookie
        assert "secure" in cookie
        assert "samesite=lax" in cookie
