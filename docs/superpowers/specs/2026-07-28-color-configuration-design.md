# Configurable Colors per Grocy User — Design Spec

## Summary

Extend the existing per-user color override (single accent `color` field) to support:
- **Per-user card background** (`card_bg`) — distinct from accent color
- **Global theme overrides** — page background, surface, text colors, overdue accent — editable from the settings page
- **Swatch-based color picker** — replaces the bare `ui.color_input` with clickable palette swatches + custom hex option

## Data Model

### `app/user_config.py`

```python
@dataclass
class UserEntry:
    id: int
    color: str | None = None       # accent (border-top + header text) — existing
    card_bg: str | None = None     # card background override (new)

@dataclass
class UserConfig:
    users: list[UserEntry] = field(default_factory=list)
    # Global theme overrides — None means "use theme.py default"
    page_bg: str | None = None
    surface: str | None = None
    text_primary: str | None = None
    text_muted: str | None = None
    overdue_accent: str | None = None
```

### JSON file format

```json
{
  "page_bg": "#1E2A24",
  "surface": null,
  "text_primary": null,
  "text_muted": null,
  "overdue_accent": "#FF6B57",
  "users": [
    { "id": 2, "color": null, "card_bg": null },
    { "id": 3, "color": "#7EC8E3", "card_bg": "#2A3D33" }
  ]
}
```

`null` = use the compiled-in `theme.py` default. Missing fields (backward compat with old files) are treated as `null`.

### `save_user_config` update

Include global override fields in the serialized payload alongside `users`.

---

## Theme Resolution

### `app/ui/theme.py` — new `ResolvedTheme` + resolver

```python
@dataclass
class ResolvedTheme:
    background: str = BACKGROUND
    surface: str = SURFACE
    text_primary: str = TEXT_PRIMARY
    text_muted: str = TEXT_MUTED
    overdue_accent: str = OVERDUE_ACCENT

def resolve_theme(overrides: UserConfig | None = None) -> ResolvedTheme:
    """Merge global overrides from UserConfig with theme.py defaults.
    Called once per dashboard refresh in chore_service.get_dashboard_data().
    """
```

Each field: `overrides.page_bg or BACKGROUND`, etc.

### `app/ui/theme.py` — `color_swatch_picker` helper

```python
def color_swatch_picker(
    current_color: str,
    on_select: Callable[[str], None],
    *,
    palette: list[str] | None = None,
    allow_custom: bool = True,
) -> None:
    """Render a row of clickable color swatches.
    Active swatch has a checkmark. 'Custom' opens an inline hex input.
    """
```

Renders in the current NiceGUI context (no return value — pure side-effect component).

---

## Model Changes

### `app/models.py` — `DashboardUser` gains `card_bg`

```python
@dataclass(frozen=True)
class DashboardUser:
    id: int
    display_name: str
    color: str       # resolved accent (deterministic or override)
    card_bg: str     # resolved card background (new — surface or override)
```

---

## Chore Service

### `app/services/chore_service.py`

In `get_dashboard_data()`:
1. Resolve `ResolvedTheme` from user config overrides once at the top
2. Pass `card_bg` through `DashboardUser` — resolved per user as `entry.card_bg or resolved_theme.surface`
3. Return `(list[UserChores], ResolvedTheme)` so the dashboard can use
   resolved theme for page-level styling (body bg, text colors)

The `ResolvedTheme` return value flows through `dashboard.py` to style the page,
and individual cards pick up their resolved `card_bg` from `DashboardUser`.

---

## Settings Page

### `app/ui/settings.py` — new layout

1. **Global Theme section** (collapsible)
   - `page_bg`, `surface`, `text_primary`, `text_muted`, `overdue_accent` — each with a swatch picker + "Use default" button
   - Preview strip showing the combined palette
   - "Reset all to defaults"

2. **Per-user rows** (existing, extended)
   - Up/down reorder (unchanged)
   - Name label (unchanged)
   - Accent color: swatch picker (replaces `ui.color_input`) + "Use default" button
   - Card BG: swatch picker + "Use default" button
   - Delete button (unchanged)

3. **Add user** (unchanged)

4. **Save changes** (unchanged)

---

## Dashboard & Card Styling

### `app/ui/dashboard.py`

- `get_dashboard_data()` returns `(list[UserChores], ResolvedTheme)` — unpack at the top of `render()`
- Page `<body>` background uses `resolved_theme.background`
- Header text uses `resolved_theme.text_primary`
- "Settings" link uses `resolved_theme.text_muted`
- Pass `resolved_theme` through to `render_user_card()` and `render_chore_row()` so they use resolved text/muted colors

### `app/ui/user_card.py`

- Accept `resolved_theme: ResolvedTheme` parameter
- Card background: `user_chores.user.card_bg` (resolved at the chore_service level)
- Header name color: uses `user_chores.user.color` (accent) — no change
- "All done!" text: uses `resolved_theme.text_muted`

### `app/ui/chore_row.py`

- Accept `resolved_theme: ResolvedTheme` parameter
- Chore name text color: uses `resolved_theme.text_primary`
- Due date text color: uses `resolved_theme.text_muted`
- Overdue left-border: uses `resolved_theme.overdue_accent`

---

## Files Modified

| File | Change |
|------|--------|
| `app/user_config.py` | New fields on `UserEntry` and `UserConfig`; update `save_user_config` serialization |
| `app/models.py` | Add `card_bg` to `DashboardUser` |
| `app/ui/theme.py` | Add `ResolvedTheme`, `resolve_theme()`, `color_swatch_picker()` |
| `app/ui/settings.py` | Global theme section; swatch pickers; card_bg per row |
| `app/ui/user_card.py` | Accept `resolved_theme` param; use `card_bg` instead of `theme.SURFACE` |
| `app/ui/chore_row.py` | Accept `resolved_theme` param; use resolved colors for text, muted, overdue |
| `app/ui/dashboard.py` | Unpack `ResolvedTheme` from `get_dashboard_data()`; pass to children; style page |
| `app/services/chore_service.py` | Resolve theme; return `(list[UserChores], ResolvedTheme)`; pass `card_bg` through DashboardUser |

No new files.
