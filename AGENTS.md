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

**Python version mismatch**: Dockerfile uses `python:3.12-slim`, `.python-version` says `3.14`, and the local `.venv` is 3.14. Don't "fix" either without understanding the intent — likely just pre-dates the Docker image updating.

## Test patterns

Tests use `pytest` with `pytest.mark.asyncio`. The one test file (`tests/test_slot_crash.py`) demonstrates:
- NiceGUI's `user_simulation` for UI interaction tests
- `patch("nicegui.ui.timer")` for unit-testing timer-based code
- `app._exception_handlers.append(...)` to capture uncaught errors in async UI tests
- `ui.timer(0.01, ..., once=True)` pattern to defer container rebuilds

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
- **`.gitignore` gaps**: doesn't cover `.env` (secrets) or `data/` (runtime user data). Be careful with git operations.
- **Syncthing sync-conflict files** (`.sync-conflict-*`) exist in the tree — ignore them; they're stale copies, not source of truth.

## Response compactness

Answer in 1-3 sentences. No preamble/postamble, no code explanation unless asked. `docs/quickref.md` has the data-model/component signatures so I don't reread sources every task.
