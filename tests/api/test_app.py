from fastapi.testclient import TestClient

from tests.api.conftest import AppFactory, Browser


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ok",
        "version": "0.1.0",
        "database": "sqlite",
        "ai": "fallback",
        "demo": False,
    }


def test_security_headers(client: TestClient) -> None:
    r = client.get("/login")
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"


def test_static_files_are_served_and_cached(client: TestClient) -> None:
    r = client.get("/static/vendor/htmx-2.0.11.min.js")
    assert r.status_code == 200
    assert "max-age" in r.headers["cache-control"]
    assert client.get("/static/css/app.css").status_code == 200


def test_404_page(user: Browser) -> None:
    r = user.get("/no-such-page")
    assert r.status_code == 404
    assert "We couldn" in r.text
    assert user.get("/recipes/123456").status_code == 404


def test_no_inline_scripts_or_styles(user: Browser) -> None:
    """The CSP forbids inline code, so templates must not contain any."""
    for path in [
        "/",
        "/pantry",
        "/recipes",
        "/recipes/new",
        "/recipes/import",
        "/plan",
        "/shopping",
        "/cook",
    ]:
        html = user.get(path).text
        assert "<script>" not in html, path
        assert " style=" not in html, path
        assert " onclick=" not in html, path


def test_openapi_docs_are_disabled(client: TestClient) -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_demo_reset_restores_data(make_app: AppFactory) -> None:
    app = make_app(demo_mode=True, demo_reset_hours=0)
    with TestClient(app, follow_redirects=False) as client:
        b = Browser(client)
        b.post("/demo-login")
        b.refresh()
        before = client.get("/api/pantry").json()["items"]
        assert any(i["name"] == "Baby spinach" for i in before)
        spinach = next(i for i in before if i["name"] == "Baby spinach")
        b.post(f"/pantry/{spinach['id']}/delete")
        # demo_reset_hours=0 means every request re-seeds.
        after = client.get("/api/pantry").json()["items"]
        assert any(i["name"] == "Baby spinach" for i in after)
