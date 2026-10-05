"""Browser tests. They start the real app with uvicorn in demo mode, or run
against an existing deployment when E2E_BASE_URL is set:

    E2E_BASE_URL=https://pantry-planner.vercel.app pytest -m e2e
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORT = int(os.environ.get("E2E_PORT", "47301"))


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "tests/e2e" in item.nodeid.replace("\\", "/"):
            item.add_marker(pytest.mark.e2e)


def _wait_for(url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:  # noqa: S310 - local URL
                if r.status == 200:
                    return
        except OSError:
            time.sleep(0.3)
    raise RuntimeError(f"server at {url} did not start")


@pytest.fixture(scope="session")
def server_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    external = os.environ.get("E2E_BASE_URL")
    if external:
        yield external.rstrip("/")
        return

    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", DEFAULT_PORT)) == 0:
            raise RuntimeError(f"port {DEFAULT_PORT} is busy; set E2E_PORT")

    db = tmp_path_factory.mktemp("e2e") / "e2e.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db}",
        "DEMO_MODE": "true",
        "SECRET_KEY": "e2e-secret",
        "ANTHROPIC_API_KEY": "",
    }
    proc = subprocess.Popen(  # noqa: S603 - fixed command line
        [sys.executable, "-m", "uvicorn", "app:app", "--port", str(DEFAULT_PORT)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{DEFAULT_PORT}"
    try:
        _wait_for(url + "/healthz")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)
