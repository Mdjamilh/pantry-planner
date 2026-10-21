# syntax=docker/dockerfile:1
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first, so code changes don't bust the layer cache.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY app.py alembic.ini ./
COPY pantry_planner ./pantry_planner

RUN useradd --create-home --uid 10001 pantry && mkdir -p /app/data && chown pantry /app/data
USER pantry

# SQLite lives in a volume by default; set DATABASE_URL for Postgres.
ENV DATABASE_URL=sqlite:////app/data/pantry-planner.db
VOLUME ["/app/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status == 200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
