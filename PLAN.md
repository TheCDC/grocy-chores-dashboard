# Implementation Plan — Grocy Chores Dashboard

## Status

This is a working implementation, not just a stub — all files below have
real logic, and the business-logic layer (`app/services/chore_service.py`,
`app/user_config.py`, `app/grocy_client.py`) is smoke-tested against the
**actual installed `grocy-py` and `nicegui` libraries** (real `Chore`/
`User` pydantic models, real `AssignmentType` enum, real `ui.notify` /
`ui.color_input` signatures) — not just guessed at from docs. See
"Confirmed against the real library" below for exactly what that testing
covered.

What's genuinely still open is listed in §6 — mostly things that need a
live Grocy instance or a real browser to verify (some Grocy timestamp/
timezone behavior, whether Quasar's undo-toast renders as expected,
real-device card sizing), not missing code.

## 1. Project layout

```
grocy-chores-dashboard/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── README.md
├── PLAN.md                    (this file)
├── config/
│   └── dashboard_users.example.json  # example of the JSON format (§5)
└── app/
    ├── __init__.py
    ├── main.py                 # NiceGUI entrypoint / app bootstrap
    ├── config.py                # env var loading & validation (deploy-time only)
    ├── user_config.py            # load/save the mutable JSON user list + colors
    ├── grocy_client.py           # thin wrapper around grocy-py
    ├── models.py                  # UI-facing dataclasses (DashboardUser, DashboardChore)
    ├── services/
    │   ├── __init__.py
    │   ├── chore_service.py       # fetch + sort + done/skip/reassign/undo logic
    │   └── polling.py              # background auto-refresh timer
    └── ui/
        ├── __init__.py
        ├── theme.py                # colors, fonts, responsive card-width tokens
        ├── dashboard.py             # page: horizontal-scroll row of user cards
        ├── user_card.py              # single user's card (header + vertical chore list)
        ├── chore_row.py               # single chore row (name, due, action buttons)
        └── settings.py                 # page: edit included users, order, colors
```

## 2. Confirmed against the real library

Rather than guess at `grocy-py`'s API surface, it was installed and
introspected directly. Confirmed correct as coded:

- `grocy.data_models.chore.Chore` fields used: `id`, `name`,
  `description`, `assignment_type`, `next_execution_assigned_to_user_id`,
  `next_estimated_execution_time`.
- `grocy.data_models.chore.AssignmentType` enum exists at that import
  path with `NO_ASSIGNMENT`, `WHO_LEAST_DID_FIRST`, `RANDOM`,
  `IN_ALPHABETICAL_ORDER` members — used to gate reassignment.
- `grocy.data_models.user.User` fields: `id`, `display_name` (+ others).
- `grocy.data_models.generic.EntityType.CHORES` exists;
  `generic.update(entity_type, object_id, data)` matches our call.
- `chores.execute(...)` (used for both mark-done and skip) returns a
  **plain dict** parsed from Grocy's JSON response — confirmed by
  reading `GrocyApiClient._do_post_request`'s source, which returns
  `resp.json()`. `ChoreService._extract_execution_id()`'s dict-with-`id`
  path is what actually fires.
- `ChoreService.get_dashboard_data()`, `.mark_done()`, `.skip()`,
  `.reassign()` (incl. the auto-assign guard raising
  `ReassignNotAllowedError`), and `.undo()` were run end-to-end against
  fake `GrocyClient`/`Chore`/`User` objects built from the real models —
  overdue-first sorting, per-user color resolution (incl. override), and
  the include-list filtering all behave as intended.
- **Request volume**: `grocy_client.list_chores()` originally called
  `chores.list(get_details=True)`, which costs **2 extra requests per
  chore** — confirmed by reading grocy-py's source
  (`Chore.get_details()` calls both `get_chore(id)` and
  `get_userfields("chores", id)` per chore). At even a modest chore
  count this is the "dozens to hundreds of requests per load" behavior,
  and it repeats on every `REFRESH_INTERVAL_SECONDS` poll plus after
  every action. Fixed: `list_chores()` now merges 2 bulk requests total
  (`chores.list(get_details=False)` for computed due-date status +
  `generic.list(EntityType.CHORES)` for master data covering every
  chore in one call) — verified to produce identical `Chore` objects to
  the old path via a mocked-client test (exact call counts asserted:
  `chores.list` × 1, `generic.list` × 1, regardless of chore count).
- Every `ui.*` call used (`color_input`, `notify` with `**kwargs`,
  `query`, `add_head_html`, `dialog`, `select`, `page`, …) exists on the
  installed NiceGUI version with the signature we assumed. `main.py`'s
  full bootstrap (`load_config` → `ChoreService` → both `@ui.page`
  registrations) runs without error using a fake `GrocyClient`.

What this testing does **not** cover: an actual running server rendered
in a browser, or a real Grocy instance's actual data (see §6).

## 3. Build order (for reference / if extending further)

1. `config.py` → 2. `grocy_client.py` → 3. `user_config.py` →
   4. `models.py` → 5. `services/chore_service.py` → 6. `ui/theme.py` →
   7. `ui/chore_row.py` → `ui/user_card.py` → `ui/dashboard.py` →
   8. `ui/settings.py` → 9. `services/polling.py` → 10. `main.py` →
   11. Dockerfile / docker-compose.yml.

This is the order the code was actually built and tested in — useful if
picking this project back up to extend it, since each layer's tests
assume the ones before it already work.

## 4. Visual direction (`ui/theme.py`)

Concept: a **kitchen chalkboard chore board** — dark slate-green
background (`BACKGROUND`), chalk-white text (`TEXT_PRIMARY`), each user's
card accented in a soft chalk-pastel color. A real, opinionated starting
point (not `#TODO` placeholders) — worth adjusting once seen on real
hardware, but not blocked on that.

- **Color-by-ID**: `get_user_color(user_id, override)` picks
  deterministically from `USER_COLOR_PALETTE[user_id % len(palette)]`,
  so a person keeps their color across restarts/reorders regardless of
  card position. `USER_CONFIG`-level `color` overrides (settings page)
  take precedence. `USER_COLOR_PALETTE` is append-only once deployed —
  reordering/removing entries reshuffles everyone's default.
- **Responsive card width** (`CARD_WIDTH_CLASSES`, Tailwind arbitrary
  values applied in `ui/user_card.py`): `88vw` by default (≈1 card
  visible on a portrait phone, with a deliberate sliver of the next card
  peeking as a scroll affordance) down to a fixed `300px`/`340px` at
  `lg`/`xl` breakpoints (≈4-5 visible on a landscape desktop, worked out
  as `viewport_width / (card_width + gap)` — see the comment above
  `CARD_WIDTH_CLASSES` for the exact math). Scroll-snap
  (`snap-x snap-mandatory` on the row, `snap-center` per card) gives
  touch-swipe a settled resting position per card.
- **Overdue signature**: `OVERDUE_ACCENT` is meant for a left-edge bar on
  overdue chore rows — not yet wired into `chore_row.py`'s markup (see §6).
- **Fonts**: `Kalam` (handwritten, for names/headers) + `Nunito` (clean
  sans, for chore text/legibility), loaded via Google Fonts in
  `ui/dashboard.py`'s `_load_fonts()`.

## 5. User config & settings page

Requirements doc §4 originally called for an exclude list of "system"
users; superseded by an **include list stored as JSON**
(`app/user_config.py`), editable at runtime from **`/settings`**
(`app/ui/settings.py`) instead of only via redeploy.

**File format** (`config/dashboard_users.example.json`):

```json
{
  "users": [
    { "id": 2, "color": null },
    { "id": 3, "color": null },
    { "id": 4, "color": "#4C7CF2" }
  ]
}
```

- Array order = dashboard card order (left to right).
- `color: null`/omitted = deterministic default from user ID (§4); a hex
  string overrides it.
- `USER_CONFIG_PATH` env var (default `/data/dashboard_users.json`);
  `docker-compose.yml` mounts `./data:/data` so settings-page edits
  persist across container recreation.
- **First run** (no file yet): `load_user_config()` raises
  `UserConfigNotFoundError` specifically (a `UserConfigError` subclass);
  both `ChoreService` and the settings page catch that one exception and
  start from an empty `UserConfig` rather than crashing — a genuinely
  malformed (but present) file still raises and is *not* swallowed
  anywhere, since that's a real bug to surface, not a first-run state.

**Settings page** (`app/ui/settings.py`) — fully wired, not stubbed:

- Lists included users, resolving display names live from
  `grocy.users.list()` each load (JSON only stores IDs + color
  overrides, so it can't go stale if a Grocy display name changes).
- Reorder via up/down buttons (swaps adjacent entries in-place).
- Color: `ui.color_input` per row, defaulting to the resolved
  (deterministic-or-override) color; a "Use default" button clears an
  override back to `None`.
- Remove, behind a confirmation dialog explaining it only affects the
  dashboard, not Grocy itself.
- Add, from a dropdown of all Grocy users (dedup-checked against the
  current list) — this is also how system/admin accounts stay excluded:
  by simply never adding them.
- Explicit "Save changes" button writes the whole file via
  `save_user_config()`.

Same no-login access model as the dashboard (requirements §3) — anyone
on the trusted LAN who finds `/settings` can change it.
`ui/dashboard.py` links to it deliberately unobtrusively, given kids are
also on this display.

## 6. Genuinely open items (need a live instance / real browser)

Everything here needs something this sandbox couldn't provide — a real
Grocy deployment with real data, or a real browser rendering the app —
not more code-writing:

- **Timestamp consistency**: `_chore_sort_key`/`_is_overdue`
  (`chore_service.py`) assume `next_estimated_execution_time` is
  consistently naive-or-aware across all chores from a given instance.
  If a live Grocy ever mixes both in one response, sorting raises
  `TypeError` — verify against real data.
- **Auto-assign overwrite behavior**: does Grocy actually overwrite a
  manual `next_execution_assigned_to_user_id` edit on chores with
  `WHO_LEAST_DID_FIRST`/`RANDOM`/`IN_ALPHABETICAL_ORDER` on next
  execution or `calculate_next_assignments()`? This is *why* reassign is
  guarded/disabled for those chores (requirements decision), but the
  guard's premise itself is worth confirming against a live instance.
- **Undo toast rendering**: `ui.notify(..., actions=[...])` is confirmed
  to be accepted by NiceGUI's signature (passes through `**kwargs` to
  Quasar), but whether Quasar actually renders a tappable "Undo" button
  from that dict shape needs a real browser — see
  `_notify_with_undo()`'s docstring in `ui/dashboard.py`.
- **Card sizing on real devices**: `CARD_WIDTH_CLASSES`'s "1 visible
  mobile / 4-5 visible desktop" math (§4) accounts for viewport width
  and card gap but not browser chrome/scrollbar quirks — check on the
  actual target hardware and adjust the breakpoint values if off by one.
- **Overdue left-edge bar**: `theme.OVERDUE_ACCENT` exists but isn't
  applied to chore row markup yet in `ui/chore_row.py` — small, purely
  visual addition.
- **Unassigned chores**: `get_dashboard_data()` currently drops any
  chore with no `next_execution_assigned_to_user_id` — there's no
  "Unassigned" card in this design. Decide if that's actually fine or if
  those need to surface somewhere.
- **Settings save UX**: reorder/color/add/remove all mutate the
  in-memory `UserConfig` immediately (so the page reflects changes as
  you make them) but only persist on explicit "Save changes" — navigating
  away without saving silently discards edits. Consider a "you have
  unsaved changes" warning, or auto-save on every mutation instead.
