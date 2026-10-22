# Pantry Planner

[![CI](https://github.com/Mdjamilh/pantry-planner/actions/workflows/ci.yml/badge.svg)](https://github.com/Mdjamilh/pantry-planner/actions/workflows/ci.yml)

A meal planner that starts from what is already in your kitchen. You keep a
pantry list with best-before dates, a recipe book and a weekly plan, and the
app works out the shopping list for you: everything the plan needs, minus what
you already have, with the units converted and added up. When something is
about to go off, "What can I cook?" suggests dishes that use it, either from
Claude or from a built-in matcher that works without any API key.

**Live demo:** https://pantry-planner-sage-six.vercel.app (press "Try the demo",
no sign-up needed)

![Pantry Planner dashboard](docs/screenshot.png)

## Features

- **Pantry with expiry dates.** Items are sorted by best-before date and tagged
  as expired, expiring soon or fine. Expired food never counts towards the
  shopping list.
- **Recipe book.** Type ingredients one per line ("200 g spaghetti",
  "2 cloves garlic, crushed"). Each recipe shows how many of its ingredients
  are already in the pantry.
- **Recipe import.** Paste a recipe from anywhere and get the title, servings,
  ingredients and steps back as an editable form before saving.
- **Weekly meal plan.** A Monday-to-Sunday grid with breakfast, lunch and
  dinner. Each planned meal has its own serving count.
- **Unit-aware shopping list.** Amounts are scaled to the planned servings,
  summed across recipes, converted between units (g/kg/oz/lb,
  ml/l/tsp/tbsp/cup) and reduced by what the pantry holds. Countable items are
  rounded up, spoon measures stay in spoons, and mismatches such as "3 cloves"
  against "1 head" of garlic are flagged instead of guessed. "Bought" moves an
  item straight into the pantry.
- **What can I cook?** Up to four dish ideas that favour the items expiring
  soonest. The page always says who answered: Claude or the built-in matcher.
- **Accounts.** Email and password sign-up, Argon2id password hashes, signed
  session cookies and CSRF protection on every form and htmx request.
- **Light and dark themes**, a responsive layout down to phone width, and pages
  that still work with JavaScript turned off.

## How the AI part works

Both AI features go through one small service (`pantry_planner/ai/service.py`)
that decides who answers.

**With `ANTHROPIC_API_KEY` set**, the app calls the Anthropic Messages API with
the `claude-haiku-5-5` model and asks for structured JSON output. The response
shape is defined as Pydantic models (`pantry_planner/ai/schemas.py`); the SDK's
`messages.parse()` sends that schema with the request and validates the reply
against it. The result is then cleaned up (lengths capped, empty entries
dropped) before it reaches a template.

What is sent is deliberately minimal:

- *What can I cook?* sends only ingredient names with the number of days until
  they expire, for example `- Spinach (expires in 1 days)`. No quantities, no
  account details, no recipe titles. Expired items are left out.
- *Recipe import* sends only the text you pasted, capped at 8,000 characters
  and wrapped in a `<recipe>` tag that the system prompt treats as data.

**Without a key**, or if a Claude call fails (network error, rate limit,
refusal, invalid output), the app answers locally instead and the page says so:

- The **matcher** (`ai/matcher.py`) scores your own recipes plus a catalog of
  15 everyday dishes. Each ingredient you have counts, weighted by how soon it
  expires (3x within the "soon" window, 1.5x within a week), and missing
  ingredients cost a little. Staples such as salt and oil are ignored. Dishes
  covering less than 40% of their ingredients are dropped. The same pantry
  always gives the same answer.
- The **parser** (`ai/recipe_parser.py`) reads the usual recipe layout: a title,
  "Serves 4", an Ingredients section and a Method section, or guesses line by
  line when there are no headings. Quantities like `1 1/2`, `½` and `2-3`
  are understood.

Claude calls are rate limited per user (12 every 10 minutes) to keep costs
predictable.

## Architecture

```
Browser (HTML + htmx 2.0.11, a little vanilla JS)
   |  forms and hx-post requests, CSRF token in a header or hidden field
   v
FastAPI app (pantry_planner/main.py)
   |- routes/        one module per page: auth, pantry, recipes, plan, shopping, cook, api
   |- templates/     Jinja2 pages and htmx partials
   |- services.py    per-user queries and the shopping list for a week
   |- shopping.py    pure functions: scale, sum, convert, subtract
   |- units.py       unit table, conversions, ingredient name matching
   |- parsing.py     "1 1/2 cups flour, sifted" -> quantity, unit, name, note
   |- ai/            Claude provider, matcher, parser, schemas
   v
SQLAlchemy 2 + Alembic  ->  SQLite (local, demo) or Postgres (DATABASE_URL)
```

Every route is server-rendered. htmx swaps in partials for the quick actions
(adding a pantry item, editing a row inline, filling a plan cell, ticking off
shopping), and each of those forms also works as a normal POST with a redirect.
The Content Security Policy allows no inline scripts or styles, so htmx's own
indicator styles are switched off and replaced in `static/css/app.css`.

The CSS is hand-written with custom properties for colour, spacing and radius,
a `prefers-color-scheme` dark palette plus a manual toggle, and CSS grid for the
dashboard, recipe cards and the week view.

## Running locally

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn app:app --reload --port 8000
```

Open http://localhost:8000 and create an account. Data goes into
`pantry-planner.db` in the project folder; migrations run on startup.

Optional settings (see `.env.example`):

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | local SQLite file | Postgres URL, e.g. `postgresql://user:pass@host/db` |
| `SECRET_KEY` | random per process | Signs the session cookie; set it in production |
| `ANTHROPIC_API_KEY` | empty | Turns on Claude; without it the local fallback answers |
| `ANTHROPIC_MODEL` | `claude-haiku-5-5` | Model used for both AI features |
| `DEMO_MODE` | off (on for Vercel without a database) | Seeds the demo account and shows the reset banner |

To try the demo account locally, run with `DEMO_MODE=true` and press
"Try the demo" on the sign-in page.

With Docker:

```bash
docker build -t pantry-planner .
docker run -p 8000:8000 -e SECRET_KEY=change-me -v pantry-data:/app/data pantry-planner
```

## Testing

```bash
uv run pytest -m "not e2e"          # unit and API tests (about 150)
uv run playwright install chromium
uv run pytest -m e2e                # browser tests against a real uvicorn server
uv run ruff check . && uv run ruff format --check .
uv run mypy                         # strict mode
```

- **Unit tests** cover unit conversion, ingredient parsing, the shopping list
  maths, the matcher, the recipe parser and the Claude provider (with a stub
  client, including the exact text that would be sent).
- **API tests** use FastAPI's `TestClient` against a migrated SQLite database:
  sign-up and login, CSRF rejection, open-redirect protection, cookie flags,
  per-user isolation for every resource, htmx partial responses, the rate
  limiter and the demo reset.
- **Postgres tests** run the migrations, the demo seed and a full request flow
  when `TEST_DATABASE_URL` is set. CI runs the suite against both SQLite and a
  Postgres 17 service.
- **Browser tests** (Playwright) cover the demo login, adding a pantry item,
  planning a meal and buying it from the shopping list, "What can I cook?",
  signing up and importing a recipe, and the theme toggle. Set
  `E2E_BASE_URL` to run them against a deployment.

CI (`.github/workflows/ci.yml`) runs lint, strict mypy, `pip-audit` on the
locked runtime dependencies, both test matrices, the browser tests and a Docker
build with a health-check smoke test.

## Deploying to Vercel

The app deploys to Vercel's Python runtime with no build step. Vercel finds the
FastAPI instance in `app.py` (also set as `tool.vercel.entrypoint` in
`pyproject.toml`) and installs the dependencies listed in `pyproject.toml`.
The whole app is one function, so every route shares the same process while it
is warm.

There is no managed database on the demo, so when `DATABASE_URL` is not set on
Vercel the app:

- uses a SQLite file in `/tmp`, migrated on cold start,
- seeds a demo account with a stocked pantry, six recipes and a planned week,
  with dates relative to today so something is always about to expire,
- re-seeds on every cold start and at most every six hours,
- shows a banner saying the demo resets, and a "Try the demo" button on the
  sign-in page.

Because the session cookie only holds a signed user id plus email, and the demo
user always has the same id, a demo session keeps working even if a request
lands on a fresh instance. Set `SECRET_KEY` in the project's environment
variables so cookies stay valid across instances, and set `DATABASE_URL` to a
Postgres database for real, persistent use. `ANTHROPIC_API_KEY` is optional.

## License

MIT, see [LICENSE](LICENSE).
