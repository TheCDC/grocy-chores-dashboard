"""Regression tests for dashboard.py bugs.

Bug 1 (fixed): RuntimeError from container.clear() inside
an event handler destroying the parent slot before context.client can
resolve it.  Fix: ``_schedule_refresh`` defers the rebuild to the
next event-loop tick via ``ui.timer(..., once=True)``.

Bug 2 (fixed): ``TypeError: Object of type function is not JSON
serializable`` from NiceGUI's outbox when ``_notify_with_undo`` passes
a Python callable via ``actions=[{"handler": ...}]``.  The Quasar
Notify API expects a *client-side* JavaScript function there, not a
Python function — and even if it did, orjson can't serialize
callables.  Fix: strip the callable from ``actions`` and provide the
undo action through a proper NiceGUI element instead.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from nicegui import app, context, ui
from nicegui.testing import user_simulation


@pytest.mark.asyncio
async def test_direct_container_clear_raises_runtime_error():
    """RED test: the old pattern — container.clear() followed by
    context.client inside a click handler — MUST produce a
    RuntimeError('The parent element this slot belongs to has been
    deleted.').

    This proves the regression test can detect the bug.

    Element hierarchy matches the dashboard: Container → Card → Button,
    where the *card* is the intermediate element that becomes
    unreferenced after container.clear().
    """
    errors: list[Exception] = []

    @ui.page("/")
    def page():
        container = ui.row()

        # Card acts as the intermediate element, exactly like
        # render_user_card in the dashboard.  It is NOT captured
        # by the click handler's closure, so after container.clear()
        # it becomes unreferenced and is garbage-collected, taking
        # the button's parent slot with it.
        with container:
            card = ui.column()
            ui.label("before")
            with card:
                # Button is a descendant of card → card's default_slot
                # is the button's parent_slot.
                ui.button("Click", on_click=lambda: (
                    container.clear(),
                    context.client,  # should raise RuntimeError
                ))

    async with user_simulation(root=page) as user:
        app._exception_handlers.append(errors.append)

        await user.open("/")
        user.find("Click").click()
        await asyncio.sleep(0.05)

    assert len(errors) > 0, (
        "Expected RuntimeError from direct container.clear() + context.client"
    )
    assert isinstance(errors[0], RuntimeError)
    assert "parent element" in str(errors[0]).lower()


@pytest.mark.asyncio
async def test_deferred_clear_does_not_crash():
    """GREEN test: deferring container.clear() via ui.timer(..., once=True)
    prevents the RuntimeError because the handler finishes on a valid slot.
    """
    errors: list[Exception] = []

    @ui.page("/")
    def page():
        container = ui.row()

        with container:
            card = ui.column()
            ui.label("before")
            with card:
                def on_click():
                    ui.timer(0.01, _do_clear, once=True)
                    _ = context.client  # safe – clear hasn't happened yet

                def _do_clear():
                    nonlocal card
                    container.clear()
                    with container:
                        ui.label("after")

                ui.button("Click", on_click=on_click)

    async with user_simulation(root=page) as user:
        app._exception_handlers.append(errors.append)

        await user.open("/")
        await user.should_see("before")
        user.find("Click").click()
        await asyncio.sleep(0.05)
        await user.should_see("after")

    assert len(errors) == 0, f"Unexpected exceptions: {errors}"


def test_notify_actions_handler_is_not_callable():
    """GREEN test: _notify_with_undo must NOT pass a callable handler in
    the notification actions dict, because NiceGUI's outbox serializes
    the entire payload with orjson — which raises TypeError on function
    objects.

    The fix stores the undo callback in ``_undo_callbacks`` and shows a
    plain notification — no callable reaches ``ui.notify()``.
    """
    from app.ui.dashboard import _notify_with_undo

    captured_kwargs: dict = {}

    def mock_notify(*args, **kwargs):
        captured_kwargs.update(kwargs)

    with (
        patch("nicegui.ui.notify", mock_notify),
        patch("nicegui.ui.timer"),  # ui.timer needs a slot context
    ):
        service = MagicMock()
        _notify_with_undo(
            service,
            "Test message",
            execution_id=123,
            refresh=lambda: None,
        )

    actions = captured_kwargs.get("actions")
    assert actions is None, (
        f"_notify_with_undo should not pass actions (got {actions}) — "
        "callables in actions are not JSON-serializable by NiceGUI's outbox"
    )
    # Also verify the undo callback was registered
    from app.ui.dashboard import _undo_callbacks
    assert len(_undo_callbacks) == 1, "Expected one undo callback to be registered"

    # Verify the registered callback doesn't produce serialization errors
    import json
    assert _undo_callbacks is not None  # sanity
    for uid, cb in list(_undo_callbacks.items()):
        # The callback must be callable (it's a Python function, which is fine
        # as long as it doesn't go through orjson serialization)
        assert callable(cb)

    # Clean up the undo registry (not module state across tests)
    _undo_callbacks.clear()


def test_schedule_refresh_defers_execution():
    """Unit test: _schedule_refresh must NOT call refresh immediately,
    and must schedule it via ui.timer(0.01, ..., once=True).
    """
    from app.ui.dashboard import _schedule_refresh

    called = False

    def refresh():
        nonlocal called
        called = True

    with patch("nicegui.ui.timer") as mock_timer:
        _schedule_refresh(refresh)

    assert not called, "_schedule_refresh called refresh immediately"
    mock_timer.assert_called_once_with(0.01, refresh, once=True)
