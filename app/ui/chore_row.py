"""A single chore row within a user's card.

Bottom-most UI component — build and visually check this in isolation
before wiring it into user_card.py (see PLAN.md build order).
"""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from app.models import DashboardChore, DashboardUser
from app.ui import theme
from app.ui.theme import ResolvedTheme


def render_chore_row(
    chore: DashboardChore,
    *,
    other_users: list[DashboardUser],
    resolved_theme: ResolvedTheme,
    on_mark_done: Callable[[int], None],
    on_skip: Callable[[int], None],
    on_reassign: Callable[[DashboardChore, int], None],
) -> None:
    """Render one chore row into the current NiceGUI container context.

    Args:
        chore: the chore to render.
        other_users: the full include-listed user roster, for the
            reassignment picker (requirements §5 — reassign UX is a
            dropdown of the same include-listed users).
        on_mark_done: callback(chore_id) — wire to ChoreService.mark_done,
            then trigger a refresh. Fires immediately on tap, no
            confirmation (decision: mark-done is the common-case, one-tap
            action this whole app exists to make fast; see chore_service
            for why skip is treated differently).
        on_skip: callback(chore_id) — wire to ChoreService.skip. Gated
            behind a confirmation dialog here (see _confirm_skip below) —
            skip is the less common, more consequential action (it can
            hide a chore that genuinely needs doing), so it gets the
            extra tap.
        on_reassign: callback(chore, new_user_id) — wire to
            ChoreService.reassign, which takes the full DashboardChore
            (not just an id) so it can enforce the auto-assign guard
            itself. Disabled (not hidden) here when
            chore.is_manually_reassignable is False, with an explanatory
            tooltip — see models.py for why some chores can't be
            manually reassigned.
    """
    overdue_style = (
        f"border-left: 4px solid {theme.OVERDUE_ACCENT}; padding-left: 8px;"
        if chore.is_overdue
        else "padding-left: 12px;"  # keep text aligned whether or not the bar is present
    )
    with ui.row().classes("items-center w-full").style(overdue_style):
        with ui.column().classes("flex-grow"):
            ui.label(chore.name).style(f"color: {theme.TEXT_PRIMARY};").classes(
                "text-lg font-semibold"
            )
            if chore.due_at is not None:
                # TODO: human-friendly relative due-date formatting
                # ("Overdue by 2 days" / "Due tomorrow"), not a raw
                # timestamp — this is a glance-at-from-across-the-room UI.
                ui.label(str(chore.due_at)).style(f"color: {theme.TEXT_MUTED};").classes(
                    "text-sm"
                )

        # No confirmation — one tap, done. See on_mark_done docstring above.
        ui.button(
            "Done",
            on_click=lambda: on_mark_done(chore.id),
        ).props("unelevated").classes(f"min-w-[{theme.MIN_TAP_TARGET_PX}px]")

        ui.button(
            "Skip",
            on_click=lambda: _confirm_skip(chore, on_skip),
        ).props("flat")

        if chore.is_manually_reassignable:
            options = {u.id: u.display_name for u in other_users}
            # TODO: replace with a proper picker (ui.select or a dialog
            # with per-user buttons/avatars, given this is touch-first —
            # a dropdown may be too fiddly on a wall tablet). Placeholder
            # wiring shown for the data flow only.
            ui.select(
                options,
                label="Reassign",
                on_change=lambda e: on_reassign(chore, e.value),
            )
        else:
            # Disabled rather than omitted, so it's visible that
            # reassignment exists but isn't available for this chore —
            # avoids "why can't I do this on some chores" confusion.
            ui.select(
                {},
                label="Reassign",
                on_change=lambda e: None,
            ).props("disable").tooltip(
                "This chore auto-assigns the next person "
                "(see its assignment settings in Grocy), so it can't be "
                "manually reassigned here."
            )


def _confirm_skip(chore: DashboardChore, on_skip: Callable[[int], None]) -> None:
    """Confirmation dialog before skipping a chore.

    Skip-only per the requirements decision — mark-done stays a single
    tap. TODO: wording/copy is a placeholder; tune once this is seen on
    real hardware (e.g. should it name the chore explicitly? current
    version does).
    """
    with ui.dialog() as dialog, ui.card():
        ui.label(f'Skip "{chore.name}"?').classes("text-lg font-semibold")
        ui.label(
            "This pushes the due date to the next occurrence without "
            "marking it done."
        ).classes("text-sm")
        with ui.row().classes("justify-end w-full gap-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Skip",
                on_click=lambda: (dialog.close(), on_skip(chore.id)),
            ).props("unelevated color=negative")
    dialog.open()
