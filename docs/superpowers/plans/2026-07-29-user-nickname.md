# User Nickname Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional `nickname` field to user config so each user can have a custom display name instead of their Grocy natural name.

**Architecture:** Add `nickname: str | None = None` to the `UserEntry` dataclass, parse it in `load_user_config()`, use `entry.nickname or raw_user.display_name` in `chore_service.py`, and add a text input for it on the settings page. `save_user_config()` auto-serializes via `asdict()` — no save-side changes needed.

**Tech Stack:** Python 3.14, NiceGUI, pytest

## Global Constraints

- `UserEntry.nickname` must default to `None` (not empty string) for backward compat with existing config files
- `load_user_config()` uses `u.get("nickname")` — same pattern as existing fields
- `save_user_config()` uses `asdict(u)` — no change needed
- The nickname must flow through `DashboardUser.display_name` to both card header and reassign picker

---

### Task 1: Add `nickname` to `UserEntry` and `load_user_config()`

**Files:**
- Modify: `app/user_config.py:34-43` (dataclass), `app/user_config.py:90` (parsing)
- Test: `tests/test_user_config.py`

- [ ] **Step 1: Add nickname field to UserEntry dataclass**

In `app/user_config.py`, add `nickname: str | None = None` after `color`:

```python
@dataclass
class UserEntry:
    id: int
    color: str | None = None
    nickname: str | None = None       # NEW
    card_bg: str | None = None
    text_color: str | None = None
    text_muted: str | None = None
```

- [ ] **Step 2: Parse nickname in load_user_config()**

In `app/user_config.py:90`, add `nickname=u.get("nickname")`:

```python
users = [UserEntry(
    id=u["id"],
    color=u.get("color"),
    nickname=u.get("nickname"),       # NEW
    card_bg=u.get("card_bg"),
    text_color=u.get("text_color"),
    text_muted=u.get("text_muted"),
) for u in raw["users"]]
```

- [ ] **Step 3: Add tests for nickname field**

Append to `tests/test_user_config.py`:

```python
def test_user_entry_nickname_defaults_to_none():
    entry = UserEntry(id=1)
    assert entry.nickname is None


def test_user_entry_nickname_can_be_set():
    entry = UserEntry(id=1, nickname="Buddy")
    assert entry.nickname == "Buddy"


def test_load_user_config_with_nickname(tmp_path: Path):
    path = tmp_path / "nickname.json"
    path.write_text(json.dumps({
        "users": [{"id": 1, "color": None, "nickname": "Momo"}]
    }))
    config = load_user_config(path)
    assert config.users[0].nickname == "Momo"


def test_load_user_config_missing_nickname_is_none(tmp_path: Path):
    """Old config without nickname field should default to None."""
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"users": [{"id": 1, "color": "#FFD166"}]}))
    config = load_user_config(path)
    assert config.users[0].nickname is None
```

- [ ] **Step 4: Run tests to verify**

```bash
pytest tests/test_user_config.py -v
```

Expected: all existing + new tests pass.

---

### Task 2: Use nickname in dashboard display name

**Files:**
- Modify: `app/services/chore_service.py:92-99`
- Test: `tests/test_chore_service.py`

- [ ] **Step 1: Use nickname in get_dashboard_data()**

In `app/services/chore_service.py`, change `display_name=raw_user.display_name` to use nickname:

```python
dashboard_user = DashboardUser(
    id=raw_user.id,
    display_name=entry.nickname or raw_user.display_name,
    color=get_user_color(raw_user.id, override=entry.color),
    card_bg=entry.card_bg or theme.surface,
    text_color=entry.text_color or theme.text_primary,
    text_muted=entry.text_muted or theme.text_muted,
)
```

- [ ] **Step 2: Add test for nickname display_name override**

Append to `tests/test_chore_service.py`:

```python
def test_dashboard_user_display_name_uses_nickname(service):
    service._load_user_config = lambda: UserConfig(
        users=[UserEntry(id=1, nickname="Buddy")],
    )
    service._client.list_users.return_value = [
        MagicMock(id=1, display_name="Alice")
    ]
    service._client.list_chores.return_value = []

    user_chores_list, _ = service.get_dashboard_data()
    assert user_chores_list[0].user.display_name == "Buddy"


def test_dashboard_user_display_name_falls_back_to_grocy_name(service):
    service._load_user_config = lambda: UserConfig(
        users=[UserEntry(id=1)],  # no nickname
    )
    service._client.list_users.return_value = [
        MagicMock(id=1, display_name="Alice")
    ]
    service._client.list_chores.return_value = []

    user_chores_list, _ = service.get_dashboard_data()
    assert user_chores_list[0].user.display_name == "Alice"
```

- [ ] **Step 3: Run tests to verify**

```bash
pytest tests/test_chore_service.py tests/test_user_config.py -v
```

Expected: all tests pass.

---

### Task 3: Add nickname input to settings page

**Files:**
- Modify: `app/ui/settings.py:108-212` (within `_render_entry_row`)

- [ ] **Step 1: Add nickname ui.input in _render_entry_row**

In `app/ui/settings.py`, after the display name label (around line 170) and before the color swatch picker, add a nickname input. Show the Grocy name as muted secondary text when a nickname is set.

In `_render_entry_row`, after the `ui.label(display_name)` and before the `color_swatch_picker` call:

```python
                with ui.column().classes("flex-grow"):
                    ui.label(display_name).style(
                        f"color: {theme.TEXT_PRIMARY};"
                    ).classes("font-medium")
                    with ui.row().classes("items-center gap-2 w-full"):
                        nickname_input = ui.input(
                            value=entry.nickname or "",
                            placeholder="Nickname (optional)",
                        ).classes("w-40").props("dense")
                        if entry.nickname:
                            ui.label(f"Grocy name: {grocy_user.display_name}").style(
                                f"color: {theme.TEXT_MUTED};"
                            ).classes("text-xs") if grocy_user else None

                        def _set_nickname(e, _entry=entry, _grocy=grocy_user):
                            val = e.value.strip() or None
                            _entry.nickname = val
                            render_entries()

                        nickname_input.on("blur", _set_nickname)
                        nickname_input.on("keydown.enter", _set_nickname)
```

Then remove the old standalone `ui.label(display_name)` at line 167-169 (since it's now inside the column above).

- [ ] **Step 2: Run the app to verify visually (manual check)**

```bash
python -m app.main
```

Visit `/settings`, add/edit a user, set a nickname, save, check the dashboard shows the nickname.

---

### Task 4: Update docs and example config

**Files:**
- Modify: `config/dashboard_users.example.json`
- Modify: `docs/quickref.md`

- [ ] **Step 1: Add nickname example to example config**

In `config/dashboard_users.example.json`, add `"nickname"` to one entry:

```json
{ "id": 2, "color": null, "nickname": "Mom" },
```

- [ ] **Step 2: Update quickref.md UserEntry signature**

Change the `UserEntry` line in `docs/quickref.md:97`:

```
@dataclass
class UserEntry: id: int; color: str|None = None; nickname: str|None = None; card_bg: str|None = None; text_color: str|None = None; text_muted: str|None = None
```

- [ ] **Step 3: Run final test suite**

```bash
pytest -v
```

Expected: all tests pass.
