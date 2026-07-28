"""Background auto-refresh for the dashboard (requirements doc §6).

Kept as a small standalone helper so ui/dashboard.py can wire it up with
one call rather than managing a `ui.timer` inline.
"""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui


def start_auto_refresh(refresh_fn: Callable[[], None], interval_seconds: int) -> ui.timer:
    """Register a recurring NiceGUI timer that calls `refresh_fn`.

    `refresh_fn` should be the dashboard's own re-fetch-and-rerender
    callback (see ui/dashboard.py). Actions taken via the UI (done/skip/
    reassign) should still trigger their own immediate refresh rather than
    waiting for this timer — see chore_service.py's action methods.

    Returns the ui.timer so the caller can cancel/adjust it if needed
    (e.g. pausing polling while a confirmation dialog is open, if that
    turns out to be worth doing).
    """
    return ui.timer(interval_seconds, refresh_fn)
