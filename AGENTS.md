# AGENTS.md — Grocy Chores Dashboard

A touch-optimized NiceGUI dashboard for Grocy chores.

## Quick start

```bash
cp .env.example .env   # edit: GROCY_BASE_URL, GROCY_API_KEY
docker compose up --build   # → http://localhost:8080
```

Local dev: `python -m app.main` (root `main.py` is a stub; real entry is `app/main.py`)

## Commands

| Action | Command |
|--------|---------|
| Run | `python -m app.main` |
| Test | `pytest` (or `pytest tests/test_slot_crash.py -v`) |
| Package mgr | `uv` (lockfile: `uv.lock`) |
| Docker | `docker compose up --build` |

No linter, formatter, or type checker config exists.

## Architecture

```
main.py → Config → GrocyClient → ChoreService → ui/{dashboard,settings}
                         ↑                           ↑
                    grocy-py pkg                 NiceGUI pkg
```

- `app/config.py` — env-var-driven, read-only at process start
- `app/grocy_client.py` — thin wrapper around grocy-py; includes `_patch_pooling()` monkey-patch adding `requests.Session` for connection pooling
- `app/services/chore_service.py` — business logic; UI-agnostic (zero NiceGUI imports), unit-testable in isolation
- `app/models.py` — `DashboardUser`, `DashboardChore`, `UserChores` dataclasses; UI layer never imports grocy-py models directly
- `app/user_config.py` — JSON include-list of users (`data/dashboard_users.json`); editable at runtime via `/settings`
- `app/ui/theme.py` — design tokens; `get_user_color()` is deterministic-by-user-id with per-user override
- `app/ui/chore_row.py` → `user_card.py` → `dashboard.py` — component hierarchy
- `app/ui/settings.py` — add/remove/reorder users + per-user color; no auth (trusted-LAN model)

## Key quirks

- **Slot-crash guard**: `container.clear()` in dashboard must be deferred via `ui.timer(0.01, refresh, once=True)` — calling it directly inside an event handler destroys the button's parent slot, causing `RuntimeError`. See `app/ui/dashboard.py:_schedule_refresh` and `tests/test_slot_crash.py`.
- **2-request chore fetch**: `GrocyClient.list_chores()` merges `chores.list(get_details=False)` + `generic.list(EntityType.CHORES)` in 2 bulk calls instead of grocy-py's default 2N+1 — intentional optimization.
- **First run**: missing `USER_CONFIG_PATH` file raises `UserConfigNotFoundError` (caught, not crash); malformed JSON raises `UserConfigError` (not caught).
- **Reassign guard**: only allowed for `assignment_type == NO_ASSIGNMENT`; UI disables picker + service enforces via `ReassignNotAllowedError`.
- **PLAN.md** is the canonical design doc (confirmed-vs-assumed sections, open items live-before-run).
- **Python 3.14** (`.python-version`). Dependencies: `nicegui>=1.4`, `grocy-py>=0.1.0`.
