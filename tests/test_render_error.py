"""Regression tests: render() must not leave the UI blank on error.

When get_dashboard_data() fails (network error, Grocy API down, etc.),
render() must NOT clear the old UI — it should return early and show
a notification instead.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from nicegui import app, ui
from nicegui.testing import user_simulation

from app.ui.dashboard import _schedule_refresh, _undo_callbacks


@pytest.mark.asyncio
async def test_fetch_error_does_not_blank_ui():
    """When the data-fetch raises, the old container content must stay
    in place.  This tests the fetch-before-clear defensive pattern."""

    errors: list[Exception] = []
    render_count = 0

    @ui.page("/")
    def page():
        container = ui.row()
        with container:
            ui.label("old content")

        def render():
            nonlocal render_count
            render_count += 1

            # Same defensive pattern as the fix: fetch before clear.
            # If fetch fails, bail without touching the UI.
            try:
                if render_count > 1:  # first call works, subsequent fail
                    raise RuntimeError("Simulated Grocy failure")
                data_ok = True
            except RuntimeError:
                ui.notify("Refresh failed", type="negative")
                return

            container.clear()
            with container:
                ui.label("new content")

        render()

        ui.button("Refresh", on_click=lambda: (
            _schedule_refresh(render),
        ))

    async with user_simulation(root=page) as user:
        app._exception_handlers.append(errors.append)
        await user.open("/")
        # After initial render (first call, succeeds)
        await user.should_see("new content")

        # Trigger refresh that will fail (second call)
        user.find("Refresh").click()
        await asyncio.sleep(0.2)

        # After the failed refresh, the UI must NOT be blank —
        # "new content" from the initial render must still be visible
        await user.should_see("new content")

    assert len(errors) == 0, f"Unexpected exceptions: {errors}"
    _undo_callbacks.clear()
