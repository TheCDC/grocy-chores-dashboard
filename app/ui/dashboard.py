"""The dashboard page: a horizontally scrollable row of user cards.

Top of the UI build order (PLAN.md) — assembles user_card.py instances
and owns the refresh/action wiring.
"""

from __future__ import annotations

from nicegui import ui

from app.models import DashboardChore, DashboardUser
from app.services.chore_service import ChoreService, ReassignNotAllowedError
from app.services.polling import start_auto_refresh
from app.ui import theme
from app.ui.user_card import render_user_card


def build_dashboard_page(chore_service: ChoreService, refresh_interval_seconds: int) -> None:
    """Register the dashboard as the NiceGUI index page.

    Call once from main.py after constructing ChoreService.
    """

    @ui.page("/")
    def dashboard_page() -> None:
        _load_fonts()
        ui.query("body").style(f"background: {theme.BACKGROUND};")

        # Small header row with a settings link (app/ui/settings.py).
        # TODO: this is a plain text link for now — on a wall-mounted
        # touch display, consider a less-discoverable placement (small
        # gear icon in a corner) so it isn't a tempting tap target for
        # kids, per the "no login" access model in requirements §3.
        with ui.row().classes("items-center justify-between w-full"):
            ui.label("Chores").style(
                f"color: {theme.TEXT_PRIMARY}; font-family: {theme.FONT_DISPLAY};"
            ).classes("text-4xl")
            ui.link("Settings", "/settings").style(f"color: {theme.TEXT_MUTED};").classes(
                "text-sm"
            )

        # Container that render() below clears and repopulates on every
        # refresh. Simplest correct approach for v1; consider NiceGUI's
        # reactive bindings later if full-redraw causes visible flicker
        # on real hardware. `snap-x snap-mandatory` + each card's
        # `snap-center` (user_card.py) gives touch-swipe a settled resting
        # position per card, which matters most at the "1 card visible"
        # mobile-portrait width (theme.CARD_WIDTH_CLASSES).
        container = ui.row().classes(
            "w-full overflow-x-auto flex-nowrap snap-x snap-mandatory"
        ).style(f"gap: {theme.CARD_GAP_PX}px;")

        empty_state = ui.column().classes("w-full items-center mt-8")
        empty_state.set_visibility(False)
        with empty_state:
            ui.label("No one's set up yet.").style(
                f"color: {theme.TEXT_PRIMARY}; font-family: {theme.FONT_DISPLAY};"
            ).classes("text-2xl")
            ui.link("Add family members in Settings", "/settings").style(
                f"color: {theme.TEXT_MUTED};"
            )

        def render() -> None:
            container.clear()
            data = chore_service.get_dashboard_data()

            if not data:
                container.set_visibility(False)
                empty_state.set_visibility(True)
                return
            container.set_visibility(True)
            empty_state.set_visibility(False)

            all_users: list[DashboardUser] = [uc.user for uc in data]

            with container:
                for user_chores in data:
                    # Color comes resolved on the user object itself
                    # (deterministic-by-id, or a user_config override) —
                    # see chore_service.get_dashboard_data() and
                    # ui/theme.get_user_color().
                    render_user_card(
                        user_chores,
                        all_users=all_users,
                        accent_color=user_chores.user.color,
                        on_mark_done=lambda chore_id, uid=user_chores.user.id: _handle_mark_done(
                            chore_service, chore_id, uid, render
                        ),
                        on_skip=lambda chore_id, uid=user_chores.user.id: _handle_skip(
                            chore_service, chore_id, uid, render
                        ),
                        on_reassign=lambda chore, new_uid: _handle_reassign(
                            chore_service, chore, new_uid, render
                        ),
                    )

        render()
        start_auto_refresh(render, refresh_interval_seconds)

        # TODO (requirements §2): explicit left/right scroll arrow
        # buttons in addition to touch-swipe, for non-touch fallback /
        # discoverability. `container` above already scrolls via touch
        # swipe (overflow-x-auto + snap); arrows would just call
        # container's underlying DOM element .scrollBy(...) via
        # ui.run_javascript, or NiceGUI's scroll_to if available on
        # whatever NiceGUI version this ends up pinned to.


def _load_fonts() -> None:
    """Pull in the Google Fonts used by theme.py. Called once per page
    load — NiceGUI/the browser dedupes repeat <link> tags across
    reconnects, but if this becomes a problem, move it to a single
    app.add_head_html registered once in main.py instead."""
    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Kalam:wght@700&'
        'family=Nunito:wght@400;700&display=swap" rel="stylesheet">'
    )


def _handle_mark_done(service: ChoreService, chore_id: int, user_id: int, refresh) -> None:
    execution_id = service.mark_done(chore_id, user_id)
    refresh()  # immediate refresh per requirements §6, not waiting on poll
    _notify_with_undo(service, "Marked done.", execution_id, refresh)


def _handle_skip(service: ChoreService, chore_id: int, user_id: int, refresh) -> None:
    # Confirmation already happened in ui/chore_row.py's _confirm_skip
    # before this was called.
    execution_id = service.skip(chore_id, user_id)
    refresh()
    _notify_with_undo(service, "Skipped.", execution_id, refresh)


def _handle_reassign(
    service: ChoreService, chore: DashboardChore, new_user_id: int, refresh
) -> None:
    try:
        service.reassign(chore, new_user_id)
    except ReassignNotAllowedError as exc:
        # Shouldn't normally happen — the UI disables reassignment for
        # these chores (ui/chore_row.py) — but ChoreService.reassign() is
        # the authoritative guard, so handle it being hit anyway (e.g. a
        # stale render).
        ui.notify(str(exc), type="warning")
        return
    refresh()


def _notify_with_undo(service: ChoreService, message: str, execution_id: int | None, refresh) -> None:
    """Show a toast for a mark-done/skip action, with an "Undo" button
    when we have an execution ID to undo (requirements: undo is exposed).

    Confirmed against the installed NiceGUI version: `ui.notify(...)`
    accepts arbitrary `**kwargs` and passes them through to the
    underlying Quasar Notify component, which supports an `actions` list
    of `{label, handler}` dicts — this is Quasar's own undo-toast
    pattern, not a NiceGUI-specific API. Not yet confirmed that Quasar
    actually renders the action button end-to-end (that needs a running
    browser, not just an import check) — verify visually once this runs
    for real, and adjust the dict shape if Quasar expects different keys
    (e.g. some Quasar versions use `handler` vs `onClick`, or need a
    `color` per action).
    """
    if execution_id is None:
        ui.notify(message)
        return

    def _undo() -> None:
        service.undo(execution_id)
        refresh()
        ui.notify("Undone.")

    try:
        ui.notify(
            message,
            actions=[{"label": "Undo", "color": "white", "handler": _undo}],
        )
    except TypeError:
        # NiceGUI version doesn't support `actions` the way we assumed —
        # fall back to a plain toast rather than losing the action
        # entirely silently. TODO: replace with whatever this NiceGUI
        # version's actual undo-toast mechanism is (or roll a small
        # custom notification component if none exists).
        ui.notify(f"{message} (undo unavailable in this UI build)")
