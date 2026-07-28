# Configurable Colors per Grocy User — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the settings page and data model to support per-user card background colors, global theme overrides, and a swatch-based color picker.

**Architecture:** Incremental extension of existing dataclasses (`UserEntry`, `UserConfig`, `DashboardUser`) + a new `ResolvedTheme` dataclass in `theme.py` merged from `UserConfig` overrides. The `ChoreService.get_dashboard_data()` return type changes from `list[UserChores]` to `tuple[list[UserChores], ResolvedTheme]`; callers unpack and thread `resolved_theme` through the component tree.

**Tech Stack:** Python 3.14, NiceGUI 3.15+, grocy-py, pytest-asyncio

## Global Constraints

- Python 3.14 minimum (`.python-version`)
- NiceGUI >=3.15.0 (`pyproject.toml`)
- No new pip dependencies
- All new JSON fields default to `None` (backward compat with existing config files)
- `ResolvedTheme` must be importable by both `services/` and `ui/` packages

---

### Task 1: Data Model — Extend UserEntry, UserConfig, DashboardUser

**Files:**
- Modify: `app/user_config.py:33-56` (add `card_bg` to `UserEntry`, global fields to `UserConfig`, update `load_user_config`/`save_user_config`)
- Modify: `app/models.py:14-21` (add `card_bg` to `DashboardUser`)
- Test: `tests/test_user_config.py` (new file)

**Interfaces:**
- Consumes: existing `UserEntry(id, color)`, `UserConfig(users)`, `DashboardUser(id, display_name, color)`
- Produces: `UserEntry(id, color, card_bg)`, `UserConfig(users, page_bg, surface, text_primary, text_muted, overdue_accent)`, `DashboardUser(id, display_name, color, card_bg)`

- [ ] **Step 1: Write failing tests for new fields**

Create `tests/test_user_config.py`:

```python
"""Tests for user_config.py new color fields."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.user_config import (
    UserConfig,
    UserConfigError,
    UserConfigNotFoundError,
    UserEntry,
    load_user_config,
    save_user_config,
)


def test_user_entry_card_bg_defaults_to_none():
    entry = UserEntry(id=1)
    assert entry.card_bg is None


def test_user_entry_card_bg_can_be_set():
    entry = UserEntry(id=1, card_bg="#111111")
    assert entry.card_bg == "#111111"


def test_user_config_global_overrides_default_to_none():
    config = UserConfig(users=[UserEntry(id=1)])
    assert config.page_bg is None
    assert config.surface is None
    assert config.text_primary is None
    assert config.text_muted is None
    assert config.overdue_accent is None


def test_user_config_global_overrides_round_trip(tmp_path: Path):
    """Save a config with global overrides and load it back."""
    path = tmp_path / "test.json"
    original = UserConfig(
        users=[UserEntry(id=2, color="#FF0000", card_bg="#111111")],
        page_bg="#123456",
        surface="#654321",
    )
    save_user_config(path, original)
    loaded = load_user_config(path)
    assert loaded.page_bg == "#123456"
    assert loaded.surface == "#654321"
    assert loaded.text_primary is None
    assert loaded.users[0].card_bg == "#111111"
    assert loaded.users[0].color == "#FF0000"


def test_load_user_config_missing_new_fields_are_none(tmp_path: Path):
    """Old config files without card_bg / global fields should load with None defaults."""
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"users": [{"id": 1, "color": "#FFD166"}]}))
    config = load_user_config(path)
    assert config.users[0].card_bg is None
    assert config.page_bg is None
```

- [ ] **Step 2: Run failing tests — expect ImportError or AttributeError**

```bash
pytest tests/test_user_config.py -v
```

Expected: tests fail with `ImportError` (file doesn't exist) or `AttributeError`.

- [ ] **Step 3: Update `UserEntry` with `card_bg` field**

In `app/user_config.py`, add `card_bg: str | None = None` after `color`:

```python
@dataclass
class UserEntry:
    id: int
    color: str | None = None
    card_bg: str | None = None
```

- [ ] **Step 4: Update `UserConfig` with global override fields**

After `users`, add the five global fields:

```python
@dataclass
class UserConfig:
    users: list[UserEntry] = field(default_factory=list)
    page_bg: str | None = None
    surface: str | None = None
    text_primary: str | None = None
    text_muted: str | None = None
    overdue_accent: str | None = None
```

- [ ] **Step 5: Update `load_user_config` to read new fields**

In the comprehension that builds `UserEntry` instances, read `card_bg`:

```python
users = [UserEntry(id=u["id"], color=u.get("color"), card_bg=u.get("card_bg")) for u in raw["users"]]
```

After building the `UserEntry` list, read global overrides from the top-level dict:

```python
return UserConfig(
    users=users,
    page_bg=raw.get("page_bg"),
    surface=raw.get("surface"),
    text_primary=raw.get("text_primary"),
    text_muted=raw.get("text_muted"),
    overdue_accent=raw.get("overdue_accent"),
)
```

- [ ] **Step 6: Update `save_user_config` to serialize global fields**

Change the payload construction from just `{"users": ...}` to include all non-None global fields:

```python
payload: dict = {}
payload["page_bg"] = config.page_bg
payload["surface"] = config.surface
payload["text_primary"] = config.text_primary
payload["text_muted"] = config.text_muted
payload["overdue_accent"] = config.overdue_accent
payload["users"] = [asdict(u) for u in config.users]
p.write_text(json.dumps(payload, indent=2) + "\n")
```

Field values of `None` serialize as JSON `null`, which `raw.get("field")` in `load_user_config` will return as `None`.

- [ ] **Step 7: Add `card_bg` to `DashboardUser` in `app/models.py`**

```python
@dataclass(frozen=True)
class DashboardUser:
    id: int
    display_name: str
    color: str
    card_bg: str
```

- [ ] **Step 8: Run tests — expect all green**

```bash
pytest tests/test_user_config.py -v
```

Expected: 5/5 passed.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: add card_bg and global theme override fields to data models"
```

---

### Task 2: Theme Resolution — ResolvedTheme, resolve_theme()

**Files:**
- Modify: `app/ui/theme.py:10-37` (add `ResolvedTheme`, `resolve_theme()`)
- Test: `tests/test_theme.py` (new file)

**Interfaces:**
- Consumes: `UserConfig(page_bg, surface, text_primary, text_muted, overdue_accent)` from Task 1
- Produces: `ResolvedTheme(background, surface, text_primary, text_muted, overdue_accent)`, `resolve_theme(overrides: UserConfig | None = None) -> ResolvedTheme`, `color_swatch_picker(...)`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for theme resolution."""
from __future__ import annotations

import pytest

from app.ui.theme import BACKGROUND, SURFACE, TEXT_PRIMARY, TEXT_MUTED, OVERDUE_ACCENT
from app.ui.theme import ResolvedTheme, resolve_theme
from app.user_config import UserConfig, UserEntry


def test_resolve_theme_uses_defaults_when_no_overrides():
    theme = resolve_theme(None)
    assert theme.background == BACKGROUND
    assert theme.surface == SURFACE
    assert theme.text_primary == TEXT_PRIMARY
    assert theme.text_muted == TEXT_MUTED
    assert theme.overdue_accent == OVERDUE_ACCENT


def test_resolve_theme_uses_defaults_when_all_none():
    config = UserConfig(users=[])
    theme = resolve_theme(config)
    assert theme.background == BACKGROUND
    assert theme.surface == SURFACE


def test_resolve_theme_applies_partial_overrides():
    config = UserConfig(users=[UserEntry(id=1)], page_bg="#000000", surface="#111111")
    theme = resolve_theme(config)
    assert theme.background == "#000000"
    assert theme.surface == "#111111"
    assert theme.text_primary == TEXT_PRIMARY  # not overridden
    assert theme.text_muted == TEXT_MUTED
    assert theme.overdue_accent == OVERDUE_ACCENT


def test_resolve_theme_applies_all_overrides():
    config = UserConfig(
        users=[UserEntry(id=1)],
        page_bg="#a", surface="#b", text_primary="#c",
        text_muted="#d", overdue_accent="#e",
    )
    theme = resolve_theme(config)
    assert theme.background == "#a"
    assert theme.surface == "#b"
    assert theme.text_primary == "#c"
    assert theme.text_muted == "#d"
    assert theme.overdue_accent == "#e"


def test_resolved_theme_fields_are_strings():
    theme = resolve_theme()
    assert isinstance(theme.background, str)
    assert isinstance(theme.surface, str)
    assert isinstance(theme.text_primary, str)
    assert isinstance(theme.text_muted, str)
    assert isinstance(theme.overdue_accent, str)
```

- [ ] **Step 2: Run failing tests**

```bash
pytest tests/test_theme.py -v
```

Expected: ImportError or AttributeError

- [ ] **Step 3: Add `ResolvedTheme` dataclass to `app/ui/theme.py`**

After `OVERDUE_ACCENT` constant, add:

```python
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable


@dataclass
class ResolvedTheme:
    background: str = BACKGROUND
    surface: str = SURFACE
    text_primary: str = TEXT_PRIMARY
    text_muted: str = TEXT_MUTED
    overdue_accent: str = OVERDUE_ACCENT
```

- [ ] **Step 4: Add `resolve_theme()` function**

```python
def resolve_theme(overrides: UserConfig | None = None) -> ResolvedTheme:
    if overrides is None:
        return ResolvedTheme()
    return ResolvedTheme(
        background=overrides.page_bg or BACKGROUND,
        surface=overrides.surface or SURFACE,
        text_primary=overrides.text_primary or TEXT_PRIMARY,
        text_muted=overrides.text_muted or TEXT_MUTED,
        overdue_accent=overrides.overdue_accent or OVERDUE_ACCENT,
    )
```

Import `UserConfig` at the top of `theme.py` (it's imported by chore_service already, no circular dependency since theme.py is lower in the dependency chain).

- [ ] **Step 5: Add `color_swatch_picker()` helper**

```python
def color_swatch_picker(
    current_color: str,
    on_select: Callable[[str], None],
    *,
    palette: list[str] | None = None,
    allow_custom: bool = True,
) -> None:
    """Render a row of clickable color swatches + optional custom hex picker."""
    from nicegui import ui

    if palette is None:
        palette = USER_COLOR_PALETTE

    current_upper = current_color.upper()

    with ui.row().classes("items-center gap-1"):
        for swatch in palette:
            is_active = swatch.upper() == current_upper
            btn = ui.button(
                icon="check" if is_active else "colorize",
                on_click=lambda c=swatch: on_select(c),
            ).props("flat dense round").style(
                f"background-color: {swatch}; "
                f"width: 28px; height: 28px; min-width: 28px;"
            )
            if is_active:
                btn.props("outline")

        if allow_custom and current_color.upper() not in {s.upper() for s in palette}:
            _custom_swatch_with_picker(current_color, on_select)


def _custom_swatch_with_picker(current_color: str, on_select: Callable[[str], None]) -> None:
    from nicegui import ui

    def open_custom_picker():
        with ui.dialog() as dialog, ui.card():
            ui.label("Custom color").classes("text-lg font-semibold")
            color_input = ui.color_input(
                label="Hex color", value=current_color,
            ).classes("w-full")
            with ui.row().classes("justify-end w-full gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Apply",
                    on_click=lambda: (
                        on_select(color_input.value),
                        dialog.close(),
                    ),
                ).props("unelevated")
        dialog.open()

    ui.button(
        icon="palette",
        on_click=open_custom_picker,
    ).props("flat dense round").tooltip("Custom color")
```

- [ ] **Step 6: Run tests — expect all green**

```bash
pytest tests/test_theme.py -v
```

Expected: 5/5 passed.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add ResolvedTheme, resolve_theme(), and color_swatch_picker()"
```

---

### Task 3: Chore Service — Return ResolvedTheme

**Files:**
- Modify: `app/services/chore_service.py:52-100` (`get_dashboard_data()` return signature + theme resolution)
- Test: `tests/test_chore_service.py` (new file)

**Interfaces:**
- Consumes: `ResolvedTheme`, `resolve_theme()` from Task 2; `DashboardUser(card_bg)` from Task 1
- Produces: `get_dashboard_data() -> tuple[list[UserChores], ResolvedTheme]`

- [ ] **Step 1: Write failing test**

```python
"""Tests for chore_service color config integration."""
from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest

from app.config import Config
from app.grocy_client import GrocyClient
from app.models import DashboardUser
from app.services.chore_service import ChoreService
from app.ui.theme import ResolvedTheme, SURFACE
from app.user_config import UserConfig, UserEntry


@pytest.fixture
def service():
    config = MagicMock(spec=Config)
    config.user_config_path = "/dev/null/nonexistent"
    client = MagicMock(spec=GrocyClient)
    return ChoreService(client, config)


def test_get_dashboard_data_returns_resolved_theme(service):
    """get_dashboard_data() should return a (list, ResolvedTheme) tuple."""
    with (
        MagicMock() as mock_config,
    ):
        # Force _load_user_config to return a config with overrides
        service._load_user_config = lambda: UserConfig(
            users=[UserEntry(id=1)],
            page_bg="#000000",
        )
        service._client.list_users.return_value = [
            MagicMock(id=1, display_name="Alice")
        ]
        service._client.list_chores.return_value = []

        result = service.get_dashboard_data()

    assert isinstance(result, tuple), "Should return a tuple"
    assert len(result) == 2
    user_chores_list, theme = result
    assert isinstance(theme, ResolvedTheme)
    assert theme.background == "#000000"


def test_dashboard_user_has_resolved_card_bg(service):
    service._load_user_config = lambda: UserConfig(
        users=[UserEntry(id=1, card_bg="#111111")],
    )
    service._client.list_users.return_value = [
        MagicMock(id=1, display_name="Alice")
    ]
    service._client.list_chores.return_value = []

    user_chores_list, _ = service.get_dashboard_data()
    assert len(user_chores_list) == 1
    assert user_chores_list[0].user.card_bg == "#111111"


def test_dashboard_user_card_bg_falls_back_to_surface(service):
    service._load_user_config = lambda: UserConfig(
        users=[UserEntry(id=1)],  # no card_bg override
    )
    service._client.list_users.return_value = [
        MagicMock(id=1, display_name="Alice")
    ]
    service._client.list_chores.return_value = []

    user_chores_list, theme = service.get_dashboard_data()
    assert user_chores_list[0].user.card_bg == SURFACE
```

- [ ] **Step 2: Run test — expect failure**

```bash
pytest tests/test_chore_service.py -v
```

Expected: tests fail because return type mismatch.

- [ ] **Step 3: Update `_load_user_config` to pass through global overrides**

No change needed — `_load_user_config()` already returns `UserConfig(users=[])` on error, and `load_user_config()` now includes global fields.

- [ ] **Step 4: Update `get_dashboard_data()` signature and body**

Change the return type and resolve theme at the top:

```python
def get_dashboard_data(self) -> tuple[list[UserChores], ResolvedTheme]:
    user_config = self._load_user_config()
    theme = resolve_theme(user_config)

    # ... existing logic to fetch users and chores ...

    # Resolve card_bg per user
    result: list[UserChores] = []
    for entry in user_config.users:
        raw_user = raw_users.get(entry.id)
        if raw_user is None:
            continue
        dashboard_user = DashboardUser(
            id=raw_user.id,
            display_name=raw_user.display_name,
            color=get_user_color(raw_user.id, override=entry.color),
            card_bg=entry.card_bg or theme.surface,
        )
        result.append(
            UserChores(
                user=dashboard_user,
                chores=chores_by_user.get(entry.id, []),
            )
        )
    return result, theme
```

Add the import: `from app.ui.theme import ResolvedTheme, resolve_theme` at the top.

- [ ] **Step 5: Run tests — expect all green**

```bash
pytest tests/test_chore_service.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Run *all* tests to check for regressions**

```bash
pytest -v
```

Expected: all existing tests + new tests pass.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: get_dashboard_data() returns ResolvedTheme and resolves card_bg"
```

---

### Task 4: Dashboard Page — Unpack and Thread ResolvedTheme

**Files:**
- Modify: `app/ui/dashboard.py:63-98` (unpack tuple, style page, thread theme)

**Interfaces:**
- Consumes: `get_dashboard_data() -> tuple[list[UserChores], ResolvedTheme]` from Task 3
- Produces: calls `render_user_card(..., resolved_theme=theme)` and `render_chore_row(..., resolved_theme=theme)`

- [ ] **Step 1: Update `render()` to unpack tuple**

```python
def render() -> None:
    container.clear()
    data, resolved_theme = chore_service.get_dashboard_data()
```

- [ ] **Step 2: Style page body and header using resolved_theme**

On each render, update the page background and header colors from the resolved theme.

For the body background, remove the initial `ui.query("body").style(...)` from `dashboard_page()` and instead apply it inside `render()` (it generates a `<style>` tag that NiceGUI applies client-side). For text colors (header, settings link), use `resolved_theme.text_primary` and `resolved_theme.text_muted` directly in the inline `style()` calls:

```python
# In render(), after resolving data/theme:
ui.query("body").style(f"background: {resolved_theme.background};")
```

- [ ] **Step 3: Parameterize header styles**

```python
with ui.row().classes("items-center justify-between w-full"):
    ui.label("Chores").style(
        f"color: {resolved_theme.text_primary}; font-family: {theme.FONT_DISPLAY};"
    ).classes("text-4xl")
    ui.link("Settings", "/settings").style(f"color: {resolved_theme.text_muted};").classes(
        "text-sm"
    )
```

- [ ] **Step 4: Thread `resolved_theme` through to `render_user_card` and `render_chore_row`**

Pass it to each `render_user_card()` call — it in turn passes it to `render_chore_row()`.

```python
render_user_card(
    user_chores,
    all_users=all_users,
    accent_color=user_chores.user.color,
    resolved_theme=resolved_theme,
    ...
)
```

- [ ] **Step 5: Run existing tests to verify no regression**

```bash
pytest -v
```

Expected: all existing tests pass (no chore_service signature change broke them).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: dashboard page unpacks ResolvedTheme and threads to children"
```

---

### Task 5: User Card — Accept and Use ResolvedTheme

**Files:**
- Modify: `app/ui/user_card.py:17-75` (accept `resolved_theme` param, use `card_bg`, use resolved text colors)

**Interfaces:**
- Consumes: `ResolvedTheme` from Task 2
- Produces: Updated `render_user_card(..., resolved_theme: ResolvedTheme)`

- [ ] **Step 1: Add `resolved_theme` parameter to `render_user_card()`**

```python
def render_user_card(
    user_chores: UserChores,
    *,
    all_users: list[DashboardUser],
    accent_color: str,
    resolved_theme: ResolvedTheme,
    on_mark_done: Callable[[int], None],
    on_skip: Callable[[int], None],
    on_reassign: Callable[[DashboardChore, int], None],
) -> None:
```

Add import: `from app.ui.theme import ResolvedTheme`

- [ ] **Step 2: Use `card_bg` for card background**

Change:
```python
f"background: {theme.SURFACE}; "
```
to:
```python
f"background: {user_chores.user.card_bg}; "
```

- [ ] **Step 3: Use `resolved_theme.text_muted` for "All done!" text**

Change:
```python
ui.label("All done! 🎉").style(
    f"color: {theme.TEXT_MUTED}; ..."
)
```
to:
```python
ui.label("All done! 🎉").style(
    f"color: {resolved_theme.text_muted}; ..."
)
```

- [ ] **Step 4: Thread `resolved_theme` to `render_chore_row()`**

```python
render_chore_row(
    chore,
    other_users=other_users,
    resolved_theme=resolved_theme,
    on_mark_done=on_mark_done,
    on_skip=on_skip,
    on_reassign=on_reassign,
)
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: user_card uses card_bg and resolved_theme"
```

---

### Task 6: Chore Row — Accept and Use ResolvedTheme

**Files:**
- Modify: `app/ui/chore_row.py:17-102` (accept `resolved_theme` param, use resolved colors)

**Interfaces:**
- Consumes: `ResolvedTheme` from Task 2

- [ ] **Step 1: Add `resolved_theme` parameter to `render_chore_row()`**

```python
def render_chore_row(
    chore: DashboardChore,
    *,
    other_users: list[DashboardUser],
    resolved_theme: ResolvedTheme,
    on_mark_done: Callable[[int], None],
    on_skip: Callable[[int], None],
    on_reassign: Callable[[DashboardChore, int], None],
) -> None:
```

Add import: `from app.ui.theme import ResolvedTheme`

- [ ] **Step 2: Use `resolved_theme.text_primary` for chore name**

```python
ui.label(chore.name).style(f"color: {resolved_theme.text_primary};").classes(...)
```

- [ ] **Step 3: Use `resolved_theme.text_muted` for due date**

```python
ui.label(str(chore.due_at)).style(f"color: {resolved_theme.text_muted};").classes(...)
```

- [ ] **Step 4: Use `resolved_theme.overdue_accent` for overdue border**

```python
overdue_style = (
    f"border-left: 4px solid {resolved_theme.overdue_accent}; padding-left: 8px;"
    if chore.is_overdue
    else "padding-left: 12px;"
)
```

- [ ] **Step 5: Run tests to verify no regression**

```bash
pytest -v
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: chore_row uses resolved_theme for text and overdue colors"
```

---

### Task 7: Settings Page — Global Theme Section and Swatch Pickers

**Files:**
- Modify: `app/ui/settings.py:27-163` (add global theme section, replace color_input with swatch picker, add card_bg picker)

**Interfaces:**
- Consumes: `color_swatch_picker()` from Task 2, `ResolvedTheme`, `resolve_theme()` from Task 2

- [ ] **Step 1: Add import for theme helpers**

```python
from app.ui.theme import (
    BACKGROUND, SURFACE, TEXT_PRIMARY, TEXT_MUTED, OVERDUE_ACCENT,
    ResolvedTheme, resolve_theme, color_swatch_picker, get_user_color,
)
```

- [ ] **Step 2: Add "Global Theme" section between back-link and user list**

After the `ui.label("Settings")` header and before the `ui.label("Users on the dashboard")`, add:

```python
# --- Global Theme section ---
with ui.expansion("Global Theme", icon="palette").classes("w-full mt-4"):
    ui.label("Customize the dashboard's overall color scheme.").style(
        f"color: {theme.TEXT_MUTED};"
    ).classes("text-sm")

    theme_overrides = {
        "page_bg": (user_config.page_bg, BACKGROUND, "Page background"),
        "surface": (user_config.surface, SURFACE, "Card default background"),
        "text_primary": (user_config.text_primary, TEXT_PRIMARY, "Primary text"),
        "text_muted": (user_config.text_muted, TEXT_MUTED, "Muted text"),
        "overdue_accent": (user_config.overdue_accent, OVERDUE_ACCENT, "Overdue accent"),
    }

    for field_name, (current_val, default_val, label) in theme_overrides.items():
        resolved_val = current_val or default_val
        with ui.row().classes("items-center gap-2 w-full"):
            ui.label(label).style(f"color: {theme.TEXT_PRIMARY};").classes("w-40")
            color_swatch_picker(
                current_color=resolved_val,
                on_select=lambda c, f=field_name: (
                    setattr(user_config, f, c),
                    render_entries(),
                ),
            )
            if current_val is not None:
                ui.button("Default", on_click=lambda f=field_name: (
                    setattr(user_config, f, None),
                    render_entries(),
                )).props("flat dense")

    with ui.row().classes("items-center gap-2 mt-2"):
        ui.button("Reset all to defaults", on_click=lambda: (
            setattr(user_config, "page_bg", None),
            setattr(user_config, "surface", None),
            setattr(user_config, "text_primary", None),
            setattr(user_config, "text_muted", None),
            setattr(user_config, "overdue_accent", None),
            render_entries(),
        )).props("flat")
```

- [ ] **Step 3: Replace `ui.color_input` with `color_swatch_picker` in per-user rows**

In `_render_entry_row`, replace the `ui.color_input` call with the swatch picker. Replace the `set_color` helper with `_set_accent` that uses the same closure pattern:

```python
def _set_accent(color: str | None) -> None:
    entry.color = color or None
    render_entries()

# Remove:
# ui.color_input(
#     label="Color",
#     value=entry.color or resolved_color,
#     on_change=lambda e: set_color(e.value),
# ).classes("w-40").props("dense")

# Replace with:
color_swatch_picker(
    current_color=entry.color or resolved_color,
    on_select=_set_accent,
)
if entry.color is not None:
    ui.button("Use default", on_click=lambda: _set_accent(None)).props(
        "flat dense"
    )
```

- [ ] **Step 4: Add `card_bg` swatch picker to per-user rows**

In each user row, after the accent color picker, add a card BG swatch picker. The default (when `entry.card_bg is None`) is `theme.SURFACE`:

```python
def _set_card_bg(color: str | None) -> None:
    entry.card_bg = color or None
    render_entries()

# Card BG picker
ui.label("BG").style(f"color: {theme.TEXT_MUTED};").classes("text-xs")
color_swatch_picker(
    current_color=entry.card_bg or SURFACE,
    on_select=_set_card_bg,
)
if entry.card_bg is not None:
    ui.button("Use default", on_click=lambda: _set_card_bg(None)).props(
        "flat dense"
    )
```

- [ ] **Step 5: Update `render_entries` to re-resolve on every render**

Since global theme overrides affect the resolved card_bg default, the `render_entries()` function that rebuilds the per-user rows is already fine — it's called on every mutation.

- [ ] **Step 6: Run tests to verify no regression**

```bash
pytest -v
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: settings page — global theme section and swatch pickers"
```

---

### Task 8: Verify the Full Flow End-to-End

- [ ] **Step 1: Run all tests one final time**

```bash
pytest -v
```

Expected: all tests green.

- [ ] **Step 2: Quick smoke check**

Verify imports resolve correctly (the app can start without a Grocy instance):

```bash
python -c "from app.config import load_config; from app.grocy_client import GrocyClient; from app.services.chore_service import ChoreService; from app.ui.theme import ResolvedTheme, resolve_theme, color_swatch_picker; print('All imports OK')"
```

Expected: "All imports OK"

- [ ] **Step 3: Final commit (if any outstanding changes)**

```bash
git status
```

If clean, done. If changes, commit them.

- [ ] **Step 4: Update PLAN.md**

Note in PLAN.md §6 that the color override open item is now implemented.
