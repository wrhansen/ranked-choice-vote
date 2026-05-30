# Ranked Choice Voting App — Implementation Plan

## Overview

Django 5.2 / HTMX ranked-choice voting app. Anonymous users (identified by session) join active polls and submit a ranked ordering of options. A Django admin superuser manages everything. Three counting algorithms are supported, selectable per poll.

---

## Phase 1: Project Scaffolding

Set up the base project skeleton.

**Files to create:**
- `Dockerfile` — Python 3.14-slim, installs requirements, copies source
- `docker-compose.yml` — `web` service with volume mounts for code and media, port 8000
- `requirements.txt` — Django 5.2, Pillow (ImageField), gunicorn
- `manage.py` + `config/` Django project (settings, urls, wsgi)
- `voting/` Django app (models, views, admin, urls)
- `.env.example` — SECRET_KEY, DEBUG, ALLOWED_HOSTS

Settings: SQLite db at `db.sqlite3`, MEDIA_ROOT at `media/`, STATIC_ROOT, installed apps.

---

## Phase 2: Models (`voting/models.py`)

```
Poll
  id             UUIDField  primary_key=True  default=uuid.uuid4  editable=False
  title          CharField
  state          CharField  choices: NEW | ACTIVE | CLOSED  default: NEW
  algorithm      CharField  choices: IRV | BORDA | CONDORCET
  created_at     DateTimeField  auto
  closed_at      DateTimeField  null=True blank=True  (set when admin closes the poll)

Option
  poll           FK(Poll, CASCADE)
  title          CharField
  image          ImageField  upload_to='options/'
  order          PositiveIntegerField  (display ordering)

UserPoll  ← join record; source of truth for participant/voted counts and live status
  poll           FK(Poll, CASCADE)
  name           CharField  (entered by user on join)
  session_key    CharField  (request.session.session_key)
  ip_address     GenericIPAddressField
  joined_at      DateTimeField  auto
  has_voted      BooleanField  default: False
  unique_together: (poll, session_key)

Vote
  poll           FK(Poll, CASCADE)
  user_poll      OneToOneField(UserPoll, CASCADE)
  rankings       JSONField  (ordered list of Option PKs, index 0 = 1st choice)
  submitted_at   DateTimeField  auto
```

---

## Phase 3: Algorithm Layer (`voting/algorithms/`)

### Abstract base (`base.py`)

```python
class RankedChoiceAlgorithm:
    label: str  # display name
    def compute(self, votes: list[list[int]], options: list[Option]) -> dict:
        # returns: {"winner": Option, "summary": <algorithm-specific structure>}
        raise NotImplementedError
```

### `irv.py` — Instant Runoff Voting

- Each round: tally first-choice votes among remaining options
- Eliminate the lowest; repeat until one has majority
- Summary: list of rounds `[{"eliminated": Option, "tallies": {option_pk: count}}]`

### `borda.py` — Borda Count

- N options: 1st choice = N-1 pts, 2nd = N-2, …, last = 0
- Winner: highest total
- Summary: `[{"option": Option, "points": int}]` sorted descending

### `condorcet.py` — Schulze Method

- Build pairwise preference matrix from all votes
- Compute strongest paths (Floyd-Warshall variant on win margins)
- Winner: option whose strongest path beats all others
- Summary: pairwise win/loss matrix for display

### Registry (`__init__.py`)

```python
ALGORITHMS = {
    "IRV": IRVAlgorithm,
    "BORDA": BordaAlgorithm,
    "CONDORCET": SchulzeAlgorithm,
}
```

`Poll.compute_results()` — convenience method that looks up the algorithm from the registry and calls `compute()` with the poll's votes.

---

## Phase 4: Algorithm Unit Tests (`voting/tests/test_algorithms.py`)

Each algorithm gets a dedicated test class. Tests use plain Python lists (no DB) — `compute()` takes `votes: list[list[int]]` and `options: list[Option]`.

**IRV tests:**
- Single option → winner by default
- Clear majority on first round (no elimination needed)
- Elimination required: candidate A leads round 1 but loses after B is eliminated and its votes redistribute
- Tie on last place — deterministic tiebreak (eliminate by lowest original order)
- All votes identical

**Borda Count tests:**
- Single voter — points equal rank positions
- Multiple voters — correct point totals, correct winner
- Tie in points — deterministic tiebreak

**Condorcet / Schulze tests:**
- Clear Condorcet winner (beats all others head-to-head)
- Condorcet cycle (A>B, B>C, C>A) — Schulze strongest-path resolves correctly
- Known reference example: Schulze's own published example (verifiable ground truth)
- Single voter
- All voters agree

Run with:
```
docker compose run web python manage.py test voting.tests.test_algorithms
```

---

## Phase 5: Views & URLs

| URL | View | Notes |
|-----|------|-------|
| `/` | `HomeView` | List all polls; filter tabs for ACTIVE / CLOSED |
| `/poll/<uuid>/` | `PollView` | State-aware: join / vote / results depending on poll state and UserPoll record |
| `/poll/<uuid>/join/` | `JoinView` | POST; creates UserPoll with name; returns HTMX partial |
| `/poll/<uuid>/vote/` | `VoteView` | POST; validates rankings JSON, creates Vote + sets `UserPoll.has_voted` |
| `/poll/<uuid>/stream/` | `PollSSEView` | GET; `StreamingHttpResponse` streaming SSE events with live poll status |

Session: ensure `request.session.create()` is called before creating UserPoll if no session key exists.

---

## Phase 6: Django Admin (`voting/admin.py`)

**PollAdmin:**
- `list_display`: title, state, algorithm, created_at, participant count, voted count
- `readonly_fields`: computed results block (shown when CLOSED)
- Custom actions:
  - `activate_poll` — NEW → ACTIVE
  - `close_poll` — ACTIVE → CLOSED (sets `closed_at`, triggers result computation)
  - `copy_options_from_previous` — copies all Options from the most recent prior Poll, excluding the winner
- `ShareLinkWidget` — read-only field showing the full vote URL with a copy button

**OptionInline:** StackedInline on Poll with image preview thumbnail.

---

## Phase 7: Templates & HTMX (`voting/templates/voting/`)

**`base.html`** — Solarized theme CSS vars; theme toggle; HTMX; HTMX SSE extension (`htmx-ext-sse`); SortableJS CDN

**`home.html`** — poll list with state badges and filter tabs

**`poll.html`** — single state-aware template:
- `NEW`: "This poll hasn't started yet."
- `ACTIVE + not joined`: Join form — name input + submit (`hx-post`, `hx-target="#join-area"`)
- `ACTIVE + joined + not voted`: drag-and-drop ranking card list + submit button
- `ACTIVE + joined + voted`: waiting screen with live SSE status
- `CLOSED`: results block (winner card + algorithm-specific summary)

**Drag-and-drop ranking:**
- SortableJS on the options list
- Hidden `<input name="rankings">` updated on sort
- HTMX POST on submit

**SSE live updates:**
- `<div hx-ext="sse" sse-connect="/poll/<uuid>/stream/" sse-swap="poll-status">` wraps the status area
- `PollSSEView` is a `StreamingHttpResponse` generator that queries the DB every 2s and yields:
  ```
  event: poll-status
  data: <rendered _poll_status.html partial>

  ```
- No Django Channels or Redis required

**Partials:**
- `_join_confirm.html` — "you've joined as {name}"; swapped in on join POST
- `_poll_status.html` — joined count, voted count, participant name list; streamed via SSE
- `_results.html` — winner + algorithm-specific summary table

---

## Phase 8: Theming (`static/css/styles.css`)

CSS custom properties for Solarized Light and Dark palettes. `prefers-color-scheme` media query sets default; `data-theme` attribute on `<html>` overrides. Theme toggle writes to `localStorage` and sets the attribute.

---

## Phase 9: Deployment Config

**`fly.toml`** — app name, region, HTTP service on port 8000, persistent volume mounted at `/app/media` and `/app/data` (for SQLite)

**`.github/workflows/deploy.yml`** — on push to `main`: `flyctl deploy --remote-only`

---

## Implementation Order

1. Project scaffolding (Docker, Django project, app skeleton)
2. Models + migrations
3. Algorithm layer
4. Algorithm unit tests
5. Views + URLs
6. Django admin customizations
7. Templates + HTMX + SSE
8. CSS theming
9. Deployment config

---

## End-to-End Verification

1. `docker compose up` — server starts on :8000
2. `docker compose run web python manage.py migrate && createsuperuser`
3. Admin: create a Poll (pick algorithm), add Options with images, activate it
4. Open the vote URL in two browser tabs (different sessions); join with a name, rank options, submit
5. Verify SSE live counts update in real time across tabs
6. Admin: close the poll; vote page shows winner + algorithm summary
7. Repeat with each of the 3 algorithms
8. `docker compose run web python manage.py test` — all algorithm tests pass
