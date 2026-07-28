# Grocy Chores Dashboard

A touch-optimized, self-hosted family dashboard for [Grocy](https://grocy.info/)
chores, built with [NiceGUI](https://nicegui.io/) and
[grocy-py](https://github.com/iamkarlson/grocy-py).

> **Status: implemented, tested against the real libraries, not yet run
> against a live Grocy instance or in a real browser.** Every module's
> business logic has been smoke-tested against the actual installed
> `grocy-py`/`nicegui` packages (real pydantic models, real enum values,
> real method signatures) — see `PLAN.md` §2 for exactly what that
> covered, and §6 for the handful of things that genuinely need a live
> Grocy instance or a browser to verify.

## Quick start

```bash
cp .env.example .env
# edit .env: set GROCY_BASE_URL, GROCY_API_KEY

docker compose up --build
# → http://localhost:8080          (dashboard)
# → http://localhost:8080/settings (add users, reorder cards, set colors)
```

No need to hand-write the JSON user config first — `/settings` works from
an empty/missing state and creates `data/dashboard_users.json` on first
save. (You can also seed it from `config/dashboard_users.example.json` if
you'd rather edit JSON directly.)

## Local dev without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export $(cat .env | xargs)   # or use python-dotenv / your own approach
python -m app.main
```

## What it does

- One card per included Grocy user, chores listed vertically, sorted
  overdue-first (matches Grocy's own chores table ordering).
- Cards scroll horizontally — sized responsively so ~1 is visible on a
  portrait phone and ~4-5 on a landscape desktop (see `PLAN.md` §4 for
  the sizing math).
- Per chore: **Done** (one tap, no confirmation), **Skip** (confirmation
  dialog first — it's the more consequential action), and **Reassign**
  (disabled, with an explanatory tooltip, for chores Grocy auto-assigns —
  i.e. anything except `assignment_type: NO_ASSIGNMENT`).
- Mark-done and skip both show an **Undo** toast right after, wired to
  `grocy.chores.undo()`.
- Auto-refreshes on a timer (`REFRESH_INTERVAL_SECONDS`), plus an
  immediate refresh after any action.
- `/settings` — add/remove/reorder users and set per-user color
  overrides, without touching the JSON file or restarting the container.

## Where to look

- `PLAN.md` — what's confirmed against the real libraries, the visual
  direction, the user-config format, and the genuinely open items.
- `app/services/chore_service.py` — the core business logic: fetch,
  translate, filter to included users, sort, and the done/skip/reassign/
  undo actions (including the reassign auto-assign guard).
- `app/user_config.py` — the JSON file behind included users, card
  order, and color overrides. Editable at runtime from `/settings`.
- `app/grocy_client.py` — the exact grocy-py calls this app depends on,
  each documented with what's confirmed vs. still assumed.
- `app/ui/` — NiceGUI components: `chore_row.py` → `user_card.py` →
  `dashboard.py`, plus `settings.py` for the users/order/color editor.

## Included users & colors

Controlled by `data/dashboard_users.json` (path via `USER_CONFIG_PATH`),
not an env var — editable from `/settings` without a redeploy. Colors are
deterministic from each person's Grocy user ID by default (same person,
same color, every time); set an explicit `color` per user (via
`/settings` or directly in the JSON) to override that. See `PLAN.md` §4-5.
