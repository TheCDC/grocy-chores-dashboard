"""The dashboard page: a horizontally scrollable row of user cards.

Top of the UI build order (PLAN.md) — assembles user_card.py instances
and owns the refresh/action wiring.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from nicegui import ui

from app.models import DashboardChore, DashboardUser
from app.services.chore_service import ChoreService, ReassignNotAllowedError
from app.services.polling import start_auto_refresh
from app.ui import theme
from app.ui.user_card import render_user_card

# Module-level registry for undo callbacks.  Keyed by a random hex string
# (not execution_id) so multiple quick actions don't collide.
_undo_callbacks: dict[str, Callable[[], None]] = {}


def build_dashboard_page(chore_service: ChoreService, refresh_interval_seconds: int) -> None:
    """Register the dashboard as the NiceGUI index page.

    Call once from main.py after constructing ChoreService.
    """

    @ui.page("/")
    def dashboard_page() -> None:
        _load_fonts()

        # Header area — rebuilt on each render so theme updates propagate.
        header_area = ui.row().classes("items-center justify-between w-full")

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

        # Undo bar — lives outside the container so it survives re-renders.
        undo_bar = ui.row().classes("w-full justify-end mt-4")
        undo_bar.set_visibility(False)

        def _refresh_undo_bar() -> None:
            """Rebuild the undo action buttons from _undo_callbacks."""
            undo_bar.clear()
            if not _undo_callbacks:
                undo_bar.set_visibility(False)
                return

            with undo_bar:
                for uid, callback in list(_undo_callbacks.items()):
                    def make_handler(_uid=uid, _cb=callback):
                        _undo_callbacks.pop(_uid, None)
                        _cb()
                        _refresh_undo_bar()

                    ui.button("Undo", on_click=make_handler).props("flat color=primary")
            undo_bar.set_visibility(True)

        def render() -> None:
            header_area.clear()
            container.clear()
            data, resolved_theme = chore_service.get_dashboard_data()
            ui.query("body").style(f"background: {resolved_theme.background};")

            with header_area:
                ui.label("Chores").style(
                    f"color: {resolved_theme.text_primary}; font-family: {theme.FONT_DISPLAY};"
                ).classes("text-4xl")
                ui.link("Settings", "/settings").style(
                    f"color: {resolved_theme.text_muted};"
                ).classes("text-sm")

            if not data:
                container.set_visibility(False)
                empty_state.clear()
                with empty_state:
                    ui.label("No one's set up yet.").style(
                        f"color: {resolved_theme.text_primary}; font-family: {theme.FONT_DISPLAY};"
                    ).classes("text-2xl")
                    ui.link("Add family members in Settings", "/settings").style(
                        f"color: {resolved_theme.text_muted};"
                    )
                empty_state.set_visibility(True)
                return
            container.set_visibility(True)
            empty_state.set_visibility(False)

            all_users: list[DashboardUser] = [uc.user for uc in data]

            with container:
                for user_chores in data:
                    render_user_card(
                        user_chores,
                        all_users=all_users,
                        accent_color=user_chores.user.color,
                        resolved_theme=resolved_theme,
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

            _refresh_undo_bar()

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


def _schedule_refresh(refresh) -> None:
    """Defer a dashboard refresh to the next event-loop tick.

    ``render()`` calls ``container.clear()`` which destroys every child
    element (including the button whose click handler is currently
    executing).  Calling ``refresh`` directly inside an event handler
    leaves NiceGUI's context machinery pointing at a deleted slot,
    causing ``RuntimeError: The parent element this slot belongs to has
    been deleted.``  A one-shot timer avoids this by letting the current
    handler finish completely on the still-valid slot before the rebuild.
    """
    ui.timer(0.01, refresh, once=True)


def _handle_mark_done(service: ChoreService, chore_id: int, user_id: int, refresh) -> None:
    execution_id = service.mark_done(chore_id, user_id)
    _notify_with_undo(service, "Marked done.", execution_id, refresh)
    _schedule_refresh(refresh)


def _handle_skip(service: ChoreService, chore_id: int, user_id: int, refresh) -> None:
    # Confirmation already happened in ui/chore_row.py's _confirm_skip
    # before this was called.
    execution_id = service.skip(chore_id, user_id)
    _notify_with_undo(service, "Skipped.", execution_id, refresh)
    _schedule_refresh(refresh)


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
    _schedule_refresh(refresh)


def _notify_with_undo(service: ChoreService, message: str, execution_id: int | None, refresh) -> None:
    """Show a toast for a mark-done/skip action, and register an undo
    button in the dashboard's undo bar.

    Quasar's ``Notify`` API supports ``actions=[{handler,...}]`` but
    ``handler`` must be a *client-side* JavaScript function — not a
    Python callable.  Passing a Python function through would cause
    a ``TypeError`` when NiceGUI's outbox serializes the payload with
    orjson.  Instead we store the callback in ``_undo_callbacks`` and
    render the undo button with a proper NiceGUI ``on_click`` handler
    via ``_refresh_undo_bar``.
    """
    if execution_id is None:
        ui.notify(message)
        return

    uid = uuid4().hex

    def _undo() -> None:
        _undo_callbacks.pop(uid, None)
        try:
            service.undo(execution_id)
        except Exception:
            pass
        _schedule_refresh(refresh)
        ui.notify("Undone.")

    _undo_callbacks[uid] = _undo
    ui.timer(15.0, lambda: _undo_callbacks.pop(uid, None), once=True)
    ui.notify(message, type="positive", position="bottom-right")
