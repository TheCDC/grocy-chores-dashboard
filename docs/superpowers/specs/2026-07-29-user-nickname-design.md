# User Nickname — Design Doc

Add a `nickname` field to the user config so each user can have a custom
display name instead of the natural name from Grocy.

## Scope

Single, self-contained change touching 3 files in `app/` + 2 doc files.

## Data model

```python
# app/user_config.py
@dataclass
class UserEntry:
    id: int
    color: str | None = None
    nickname: str | None = None       # NEW — overrides Grocy display name
    card_bg: str | None = None
    text_color: str | None = None
    text_muted: str | None = None
```

`nickname` is entirely optional — `None` means "use Grocy's natural name."

## Loading

`load_user_config()` reads `u.get("nickname")` — same pattern as the
existing `u.get("color")`, `u.get("card_bg")`, etc. No new validation
(empty string is treated truthily; callers can `entry.nickname or None`
if desired later).

## Saving

`save_user_config()` already uses `asdict(u)` on each `UserEntry`, so
`nickname` is serialized automatically — no save-side changes needed.

## Display name resolution

The one place `display_name` is assigned:

```python
# app/services/chore_service.py:94
display_name=entry.nickname or raw_user.display_name,
```

This flows through `DashboardUser.display_name` to both:
- Card header in `user_card.py:58`
- Reassign picker options in `chore_row.py:86`

No changes to `DashboardUser`, `user_card.py`, or `chore_row.py`.

## Settings UI

In `app/ui/settings.py:_render_entry_row`, a text input for nickname is
added after the user's row label. The label shows the resolved name
(nickname or Grocy name); the Grocy name is shown as muted secondary
text when a nickname is set.

Layout (single row, appended after the label and before the color
pickers):

```
[▲][▼] Nickname or Grocy name  [✏️ nickname input]  [color]  [Text] [Muted] [BG] [🗑️]
```

The input is a plain `ui.input` — no validation, no character limits.
Clearing the input sets nickname back to `None`.

## Example config

`config/dashboard_users.example.json` gets a `"nickname"` example entry.

## Files changed

| File | Change |
|------|--------|
| `app/user_config.py` | Add `nickname` field to `UserEntry`, parse it in `load_user_config()` |
| `app/services/chore_service.py` | Use `entry.nickname or raw_user.display_name` |
| `app/ui/settings.py` | Add nickname `ui.input` in `_render_entry_row` |
| `config/dashboard_users.example.json` | Add `"nickname"` example |
| `docs/quickref.md` | Update `UserEntry` signature |
