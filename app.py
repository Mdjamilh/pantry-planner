"""Vercel / uvicorn entrypoint: `uvicorn app:app`."""

from pantry_planner.main import create_app

app = create_app()
