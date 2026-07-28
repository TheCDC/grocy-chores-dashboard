"""A single user's card: header + vertical scrollable chore list.

Build after chore_row.py (see PLAN.md build order).
"""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from app.models import DashboardChore, DashboardUser, UserChores
from app.ui import theme
from app.ui.chore_row import render_chore_row
from app.ui.theme import ResolvedTheme


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
    """Render one user's card into the current NiceGUI container context.

    Args:
        user_chores: this user + their (already filtered/sorted) chores.
        all_users: full include-listed roster, passed through to
            chore_row's reassignment picker.
        accent_color: this card's per-user accent — resolved on
            user_chores.user.color by chore_service.get_dashboard_data()
            via ui.theme.get_user_color() (deterministic by user ID, or a
            user_config override). Passed explicitly rather than reread
            here so this component stays a pure function of its inputs.
        on_mark_done / on_skip / on_reassign: passed straight through to
            each chore_row — see chore_row.py for signatures. Threading
            these through rather than importing ChoreService directly
            keeps this component testable/renderable in isolation.
    """
    other_users = [u for u in all_users if u.id != user_chores.user.id]

    with ui.card().classes(
        f"flex-shrink-0 snap-center {theme.CARD_WIDTH_CLASSES}"
    ).style(
        f"min-height: {theme.CARD_MIN_HEIGHT_PX}px; "
        f"background: {user_chores.user.card_bg}; "
        f"border-top: 6px solid {accent_color};"
    ):
        ui.label(user_chores.user.display_name).style(
            f"color: {accent_color}; font-family: {theme.FONT_DISPLAY};"
        ).classes("text-3xl")

        if not user_chores.chores:
            # A nice "you're done" moment is worth more here than a
            # blank card — this is a family dashboard, not an admin
            # table, and finishing your chores should feel good.
            ui.label("All done! 🎉").style(
                f"color: {user_chores.user.text_muted}; font-family: {theme.FONT_BODY};"
            ).classes("text-sm mt-2")
            return

        # Vertical scrollable chore list (requirements §2).
        with ui.column().classes("w-full gap-2 overflow-y-auto mt-2").style(
            f"max-height: {theme.CARD_MIN_HEIGHT_PX - 80}px;"
        ):
            for chore in user_chores.chores:
                render_chore_row(
                    chore,
                    other_users=other_users,
                    text_color=user_chores.user.text_color,
                    text_muted=user_chores.user.text_muted,
                    resolved_theme=resolved_theme,
                    on_mark_done=on_mark_done,
                    on_skip=on_skip,
                    on_reassign=on_reassign,
                )
