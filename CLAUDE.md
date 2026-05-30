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

```bash
docker compose up                                              # start local dev server
docker compose run web python manage.py migrate               # run migrations
docker compose run web python manage.py createsuperuser       # create admin user
docker compose run web python manage.py test                  # run all tests
docker compose run web python manage.py test <app.TestClass>  # run a single test
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

- **No user accounts** — users are identified by IP address throughout.
- **Django admin** handles all management: creating Options, setting Poll state, copying options from previous polls (excluding the winner), and generating shareable links.
- **HTMX** drives the drag-and-drop ranking UI, live join/vote counters, and theme switching (Solarized Light/Dark, defaulting to system preference).
