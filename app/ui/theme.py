"""Design tokens for the dashboard.

Direction (PLAN.md §4): a warm, at-a-glance, wall-mounted family
dashboard — not a dense admin/corporate UI. Concept landed on: a kitchen
chalkboard chore board — dark slate-green "board" background, chalk-white
text, and each user's card accented in a soft chalk-pastel color. This is
a real starting point, not a placeholder — but it's still worth looking
at on real hardware and adjusting before calling it final.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.user_config import UserConfig

BACKGROUND = "#D6F5E5"  # dark chalkboard slate-green (page background)
SURFACE = "#28362F"  # card background — one step lighter than the board
TEXT_PRIMARY = "#181715"  # chalk white/cream
TEXT_MUTED = "#181A18"  # muted chalk gray-green, for due-dates/secondary text
OVERDUE_ACCENT = "#FF6B57"  # chalk coral-red, for the overdue left-edge bar


@dataclass
class ResolvedTheme:
    background: str = BACKGROUND
    surface: str = SURFACE
    text_primary: str = TEXT_PRIMARY
    text_muted: str = TEXT_MUTED
    overdue_accent: str = OVERDUE_ACCENT


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


def color_swatch_picker(
    current_color: str,
    on_select: Callable[[str], None],
    *,
    palette: list[str] | None = None,
    allow_custom: bool = True,
) -> None:
    """Compact color picker: a button showing the current color opens a
    dialog with swatches + optional custom hex input."""
    from nicegui import ui

    if palette is None:
        palette = USER_COLOR_PALETTE

    current_upper = current_color.upper()

    def open_picker():
        with ui.dialog() as dialog, ui.card().classes("gap-2"):
            ui.label("Pick a color").classes("text-lg font-semibold")

            with ui.grid(columns=3).classes("gap-1"):
                for swatch in palette:
                    is_active = swatch.upper() == current_upper
                    btn = (
                        ui.button(
                            icon="check" if is_active else "colorize",
                            on_click=lambda c=swatch: (
                                on_select(c),
                                dialog.close(),
                            ),
                        )
                        .props("flat dense round")
                        .style(
                            f"background-color: {swatch}; "
                            f"width: 28px; height: 28px; min-width: 28px;"
                        )
                    )
                    if is_active:
                        btn.props("outline")

            if allow_custom:
                ui.separator()
                ui.label("Custom").classes("text-sm")
                color_input = ui.color_input(
                    label="Hex color",
                    value=current_color,
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
        icon="colorize",
        on_click=open_picker,
    ).props("flat dense round").style(
        f"background-color: {current_color}; "
        f"width: 28px; height: 28px; min-width: 28px;"
    )


# Fixed palette that per-user colors are deterministically drawn from
# (see get_user_color() below). Soft chalk-pastel hues, distinct enough
# to tell apart at a glance and reasonably colorblind-considerate
# (varied lightness/hue, not just red vs. green).
#
# Treat this as append-only once deployed: reordering or removing an
# entry reshuffles everyone's default color, since the mapping is
# `id % len(palette)`. Add new colors at the end only.
USER_COLOR_PALETTE: list[str] = [
    "#FFD166",  # chalk yellow
    "#7EC8E3",  # chalk sky blue
    "#F49AC2",  # chalk pink
    "#8FD3A0",  # chalk mint
    "#B39DDB",  # chalk lavender
    "#FF9E7D",  # chalk coral (kept distinct from OVERDUE_ACCENT's red)
]


def get_user_color(user_id: int, override: str | None = None) -> str:
    """Resolve the accent color for a given Grocy user ID.

    Color strategy: a user's color is assigned deterministically from
    their Grocy user ID (`USER_COLOR_PALETTE[user_id % len(...)]`), so
    the same person always gets the same color across restarts/re-adds
    without needing to store anything — no two runs reshuffle colors
    just because dict/list ordering changed.

    `override` takes precedence when set — this is the per-user `color`
    field in user_config.UserEntry, editable via the settings page
    (app/ui/settings.py) for families that want to hand-pick a color
    instead of accepting the deterministic default.
    """
    if override:
        return override
    return USER_COLOR_PALETTE[user_id % len(USER_COLOR_PALETTE)]


# --- Layout -----------------------------------------------------------

# Responsive card width (Tailwind arbitrary-value classes, applied via
# .classes() in ui/user_card.py — NOT usable as a plain CSS string since
# it needs breakpoints, unlike the other tokens on this page).
#
# Target: ~1 card visible on a portrait mobile screen, ~4-5 on a
# landscape desktop screen (requirements). Worked out as:
#   - default (<640px, phone portrait): 88vw — nearly the full viewport
#     width, so exactly one card fills the screen with a small sliver of
#     the next one peeking at the edge (a deliberate hint that the row
#     scrolls, not a bug).
#   - sm/md (tablet-ish widths): scale down gradually so 2 cards start
#     to fit rather than jumping straight from 1 to 4-5.
#   - lg+ (>=1024px, typical laptop/desktop): fixed 300px. At 1280px
#     wide that's ~4 cards visible (1280 / (300+24px gap) ≈ 3.9); at
#     1920px, ~5.3.
#   - xl (>=1280px): bump to 340px so very wide monitors don't creep
#     past ~5-6 visible (1920 / (340+24) ≈ 5.3).
# Revisit on real devices — these are computed, not eyeballed, but
# viewport chrome/scrollbars/actual gap rendering will shift the exact
# count by ±1.
CARD_WIDTH_CLASSES = "w-[88vw] sm:w-[60vw] md:w-[42vw] lg:w-[300px] xl:w-[340px]"

CARD_MIN_HEIGHT_PX = 500
CARD_GAP_PX = 24

# Minimum touch target size (Apple/Google HIG guidance is ~44-48px) for
# chore action buttons (done/skip/reassign).
MIN_TAP_TARGET_PX = 48

# Google Fonts — load these in the page head (see ui/dashboard.py) rather
# than assuming they're preinstalled on whatever device renders the
# dashboard (wall tablet, random browser, etc).
FONT_DISPLAY = "'Kalam', cursive"  # chalk-handwriting feel for names/headers
FONT_BODY = "'Nunito', sans-serif"  # clean, rounded, legible at a distance/touch
