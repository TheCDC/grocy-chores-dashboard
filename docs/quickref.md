# Quick Reference — Grocy Chores Dashboard

## Data models (`app/models.py`)

```python
@dataclass(frozen=True)
class DashboardUser:
    id: int; display_name: str; color: str
    card_bg: str = ""; text_color: str = ""; text_muted: str = ""

@dataclass(frozen=True)
class DashboardChore:
    id: int; name: str; description: str | None
    assigned_user_id: int | None; due_at: datetime | None
    is_overdue: bool; is_manually_reassignable: bool  # only True for NO_ASSIGNMENT

@dataclass(frozen=True)
class UserChores:
    user: DashboardUser; chores: list[DashboardChore]
```

## Config (`app/config.py`)

- `Config` frozen dataclass: `grocy_base_url`, `grocy_api_key`, `grocy_port`, `grocy_path`, `grocy_verify_ssl`, `user_config_path` (default `/data/dashboard_users.json`), `refresh_interval_seconds` (30), `dashboard_port` (8080), `dev_reload` (False), `timezone` (America/Los_Angeles)
- `load_config()` — reads env vars, raises `ConfigError` if `GROCY_BASE_URL`/`GROCY_API_KEY`/`TZ` missing

## GrocyClient methods (`app/grocy_client.py`)

| Method | Params | Returns |
|--------|--------|---------|
| `list_chores()` | — | `list[Chore]` (2 bulk requests merged) |
| `list_users()` | — | `list[User]` |
| `mark_done(chore_id, done_by_user_id, tracked_time)` | `int, int, datetime\|None` | dict (execution entry) |
| `skip(chore_id, done_by_user_id)` | `int, int` | dict (execution entry) |
| `reassign(chore_id, new_user_id)` | `int, int` | None |
| `undo(execution_id)` | `int` | None |

## ChoreService methods (`app/services/chore_service.py`)

| Method | Params | Returns / Raises |
|--------|--------|------------------|
| `get_dashboard_data()` | — | `tuple[list[UserChores], ResolvedTheme]` |
| `mark_done(chore_id, done_by_user_id, tracked_time)` | `int, int, datetime\|None` | `int\|None` (execution ID for undo) |
| `skip(chore_id, done_by_user_id)` | `int, int` | `int\|None` |
| `reassign(chore, new_user_id)` | `DashboardChore, int` | None; raises `ReassignNotAllowedError` if not `is_manually_reassignable` |
| `undo(execution_id)` | `int` | None |

## UI component signatures (`app/ui/`)

### `chore_row.py:render_chore_row(chore, *, other_users, text_color, text_muted, resolved_theme, on_mark_done, on_skip, on_reassign)`

- `on_mark_done(chore_id)` — single tap, no confirmation
- `on_skip(chore_id)` — gated behind confirmation dialog
- `on_reassign(chore, new_user_id)` — picker disabled when `is_manually_reassignable == False`

### `user_card.py:render_user_card(user_chores, *, all_users, accent_color, resolved_theme, on_mark_done, on_skip, on_reassign)`

- Passes callbacks through to each `chore_row`

### `dashboard.py:build_dashboard_page(chore_service, refresh_interval_seconds)`

- Registers `@ui.page("/")`
- Owns `_timer_anchor` module-level hidden row for slot-crash-safe deferred refresh
- `_schedule_refresh(refresh)` — uses `ui.timer(0.01, refresh, once=True)` on `_timer_anchor`
- `_handle_mark_done`, `_handle_skip`, `_handle_reassign` — call service, schedule refresh, show undo notification
- `_undo_callbacks: dict[str, Callable]` — module-level registry, keyed by uuid hex

### `settings.py:build_settings_page(client, config)`

- Registers `@ui.page("/settings")`
- Global theme expansion, user list with reorder/color/remove, add-user dropdown, explicit Save

## Theme (`app/ui/theme.py`)

| Constant | Value |
|----------|-------|
| `BACKGROUND` | `#1E2A24` |
| `SURFACE` | `#28362F` |
| `TEXT_PRIMARY` | `#F5F1E6` |
| `TEXT_MUTED` | `#AEB8AE` |
| `OVERDUE_ACCENT` | `#FF6B57` |
| `CARD_WIDTH_CLASSES` | Tailwind arbitrary: `w-[88vw] sm:w-[60vw] md:w-[42vw] lg:w-[300px] xl:w-[340px]` |
| `CARD_MIN_HEIGHT_PX` | 500 |
| `CARD_GAP_PX` | 24 |
| `MIN_TAP_TARGET_PX` | 48 |
| `FONT_DISPLAY` | `'Kalam', cursive` |
| `FONT_BODY` | `'Nunito', sans-serif` |

- `get_user_color(user_id, override=None)` — `override` or `USER_COLOR_PALETTE[user_id % 6]`
- `resolve_theme(overrides: UserConfig\|None) -> ResolvedTheme` — merges user config overrides with defaults
- `USER_COLOR_PALETTE` — 6 chalk-pastels, append-only once deployed

## User config (`app/user_config.py`)

```python
@dataclass
class UserEntry: id: int; color: str|None = None; card_bg: str|None = None; text_color: str|None = None; text_muted: str|None = None

@dataclass
class UserConfig: users: list[UserEntry]; page_bg: str|None = None; surface: str|None = None; text_primary: str|None = None; text_muted: str|None = None; overdue_accent: str|None = None
```

- `load_user_config(path)` — `UserConfigNotFoundError` (no file), `UserConfigError` (malformed)
- `save_user_config(path, config)` — no locking, single-editor assumption

## Entrypoint (`app/main.py`)

```
load_config() → GrocyClient.from_config(config) → ChoreService(client, config)
→ build_dashboard_page(chore_service, refresh_interval)
→ build_settings_page(client, config)
→ ui.run(host="0.0.0.0", port=config.dashboard_port, ...)
```

## Key quirks

- **Slot-crash**: `container.clear()` must be deferred via `_schedule_refresh()` → `ui.timer(0.01, refresh, once=True)` on the hidden `_timer_anchor` row (outside container)
- **2-request chore fetch**: `GrocyClient.list_chores()` = `chores.list(get_details=False)` + `generic.list(EntityType.CHORES)` — avoids 2N+1 requests
- **Reassign guard**: only when `assignment_type == NO_ASSIGNMENT`; UI disables picker + `ChoreService.reassign()` enforces via `ReassignNotAllowedError`
- **Undo notification**: callbacks stored in module-level `_undo_callbacks` dict; rendered as NiceGUI buttons in undo bar (not Quasar `actions` — orjson can't serialize Python callables)
- **First run**: missing `USER_CONFIG_PATH` file → `UserConfigNotFoundError` (caught by both `ChoreService` and settings page; they start empty)
- **Malformed user config**: raises `UserConfigError` — NOT caught (real bug, surface it)
