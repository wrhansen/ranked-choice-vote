# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Ranked-choice voting application, originally designed for book club voting. Anonymous users (identified by IP) join an active poll and submit a ranked ordering of options. Django admin is the primary management interface.

## Tech Stack

- Python 3.14, Django 5.2, SQLite
- HTMX for frontend interactivity (no JS framework)
- Docker + docker-compose for local development
- Deployed to fly.io via GitHub Actions

## Development Commands

All Python/Django commands must be run inside the Docker container — do not use the local Python environment.

```bash
docker compose up                                              # start local dev server
docker compose run --rm web python manage.py migrate          # run migrations
docker compose run --rm web python manage.py createsuperuser  # create admin user
docker compose run --rm web python manage.py test             # run all tests
docker compose run --rm web python manage.py test <app.TestClass>  # run a single test
docker compose run --rm web python manage.py shell            # Django shell
```

## Domain Model

- **Poll** — the voting event; states: `NEW` → `ACTIVE` → `CLOSED`. State transitions are managed via Django admin.
- **Option** — a thing to vote on (text + image), belongs to a Poll.
- **Vote** — an ordered array of Options representing a user's ranked preference. Tied to an anonymous user by IP address.

Key rules:
- A user must *join* a Poll before submitting a Vote.
- Voting is only allowed on ACTIVE polls.
- Results are revealed once a Poll is set to CLOSED.

## Architecture Notes

- **No user accounts** — users are identified by session key; `UserPoll` records track who has joined each poll (used for live counts and preventing double-voting).
- **Django admin** handles all management: creating Options, setting Poll state, copying options from previous polls (excluding the winner), and generating shareable links.
- **HTMX** drives the drag-and-drop ranking UI (SortableJS), live join/vote counters (SSE via `htmx-ext-sse`), and theme switching (Solarized Light/Dark, defaulting to system preference).
- **SSE** (`/poll/<uuid>/stream/`) streams live participant status using `StreamingHttpResponse` — no Django Channels required. Each open SSE connection holds a gunicorn worker, which is acceptable for book-club scale.
- **Algorithms** live in `voting/algorithms/` with a registry in `__init__.py`. Adding a new algorithm means subclassing `RankedChoiceAlgorithm` and registering it — no view or model changes needed.

## Deployment

fly.io app: `ranked-choice-vote`. Deploys automatically on push to `main` via `.github/workflows/deploy.yml`.

**First-time setup:**
```bash
fly launch --no-deploy          # creates app and fly.toml (already committed)
fly volumes create ranked_choice_data --size 1 --region ord
fly secrets set SECRET_KEY=<long-random-string>
fly secrets set ALLOWED_HOSTS=ranked-choice-vote.fly.dev
fly secrets set CSRF_TRUSTED_ORIGINS=https://ranked-choice-vote.fly.dev
fly deploy
fly ssh console -C "python manage.py createsuperuser"
```

`start.sh` runs `migrate` + `collectstatic` then starts gunicorn on every deploy. SQLite and media files live on the persistent volume at `/data`.
