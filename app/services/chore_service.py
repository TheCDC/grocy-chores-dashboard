"""Business logic sitting between GrocyClient and the UI layer.

Kept UI-framework-agnostic (no NiceGUI imports) so it's unit-testable on
its own — construct with a GrocyClient (or a test double) and assert on
the returned UserChores list.
"""

from __future__ import annotations

from datetime import datetime

from app.config import Config
from app.grocy_client import GrocyClient
from app.models import DashboardChore, DashboardUser, UserChores
from app.ui.theme import get_user_color
from app.user_config import UserConfig, UserConfigNotFoundError, load_user_config

# grocy-py's AssignmentType enum — the exact import path is our one
# unverified assumption in this file (matches the module layout implied
# by grocy-py's docs, but wasn't directly confirmed against a live
# install). If this import ever breaks, `_is_manually_reassignable`
# below falls back to a string comparison so the app still runs — just
# fix the import path here and the try/except can be removed.
try:
    from grocy.data_models.chore import AssignmentType
except ImportError:  # pragma: no cover
    AssignmentType = None  # type: ignore[assignment]


class ReassignNotAllowedError(RuntimeError):
    """Raised when reassign() is called on a chore that auto-assigns."""


class ChoreService:
    def __init__(self, client: GrocyClient, config: Config):
        self._client = client
        self._config = config

    def _load_user_config(self) -> UserConfig:
        # Re-read on every call rather than caching at construction time,
        # so edits made via the settings page (app/ui/settings.py) take
        # effect on the dashboard's next refresh without a restart.
        try:
            return load_user_config(self._config.user_config_path)
        except UserConfigNotFoundError:
            # First run, before anyone has added a user via /settings —
            # not a real error. get_dashboard_data() will just return an
            # empty list, and ui/dashboard.py shows a friendly prompt to
            # visit /settings rather than crashing.
            return UserConfig(users=[])

    def get_dashboard_data(self) -> list[UserChores]:
        """Fetch current state and return one UserChores per included user,
        in the order given by the user config file (app/user_config.py —
        the JSON include list controls both filtering and card order).
        """
        user_config = self._load_user_config()
        raw_users = {u.id: u for u in self._client.list_users()}
        raw_chores = self._client.list_chores()

        chores_by_user: dict[int, list[DashboardChore]] = {}
        for raw_chore in raw_chores:
            dashboard_chore = _to_dashboard_chore(raw_chore)
            if dashboard_chore.assigned_user_id is None:
                # Unassigned chores don't appear on anyone's card in this
                # v1 — there's no "unassigned" card in the horizontal-
                # scroll design. TODO: decide if these should surface
                # somewhere (e.g. a dedicated "Unassigned" card) rather
                # than silently disappearing from the dashboard.
                continue
            chores_by_user.setdefault(dashboard_chore.assigned_user_id, []).append(
                dashboard_chore
            )

        for user_chores in chores_by_user.values():
            user_chores.sort(key=_chore_sort_key)

        result: list[UserChores] = []
        for entry in user_config.users:
            raw_user = raw_users.get(entry.id)
            if raw_user is None:
                # TODO: log a warning — a configured user config entry
                # doesn't exist in Grocy (typo, deleted user, etc). The
                # settings page (app/ui/settings.py) validates against
                # grocy.users.list() when adding, so this should mainly
                # happen if a user is deleted in Grocy after being added
                # here.
                continue
            dashboard_user = DashboardUser(
                id=raw_user.id,
                display_name=raw_user.display_name,
                color=get_user_color(raw_user.id, override=entry.color),
            )
            result.append(
                UserChores(
                    user=dashboard_user,
                    chores=chores_by_user.get(entry.id, []),
                )
            )
        return result

    # --- Actions -------------------------------------------------------
    #
    # Each of these triggers an immediate re-fetch of dashboard data
    # afterward (requirements §6 — actions shouldn't wait for the next
    # poll cycle) — that re-fetch is done by the caller, ui/dashboard.py,
    # not here, since it also owns re-rendering.

    def mark_done(self, chore_id: int, done_by_user_id: int) -> int | None:
        """Mark a chore done. No confirmation gate (decision: mark-done
        stays single-tap — see ui/chore_row.py).

        Returns an execution ID if one can be extracted from grocy-py's
        response, for the caller to power an "Undo" action — else None.
        See grocy_client.mark_done()'s docstring re: unverified return
        shape; this extraction is best-effort until that's confirmed.
        """
        result = self._client.mark_done(chore_id, done_by_user_id)
        return _extract_execution_id(result)

    def skip(self, chore_id: int, done_by_user_id: int) -> int | None:
        """Skip a chore. UI-layer confirmation happens before this is
        called (see ui/chore_row.py's _confirm_skip) — this method itself
        doesn't re-confirm.

        Returns an execution ID for "Undo", same caveat as mark_done().
        """
        result = self._client.skip(chore_id, done_by_user_id)
        return _extract_execution_id(result)

    def reassign(self, chore: DashboardChore, new_user_id: int) -> None:
        """Reassign a chore, enforcing the auto-assign guard.

        Takes the full DashboardChore (not just an id) so this can check
        `is_manually_reassignable` itself rather than trusting the UI
        layer's disabled control alone — the UI disables the reassign
        picker for these chores (see ui/chore_row.py), but this is the
        authoritative check.

        Raises:
            ReassignNotAllowedError: if the chore auto-assigns.
        """
        if not chore.is_manually_reassignable:
            raise ReassignNotAllowedError(
                f'Chore "{chore.name}" auto-assigns and cannot be '
                "manually reassigned."
            )
        self._client.reassign(chore.id, new_user_id)

    def undo(self, execution_id: int) -> None:
        """Undo a mark-done or skip. Wired to the "Undo" action shown on
        the notification right after those actions — see
        ui/dashboard.py."""
        self._client.undo(execution_id)


def _is_manually_reassignable(raw_chore) -> bool:
    """True only for chores Grocy won't auto-reassign on its own —
    i.e. `assignment_type == AssignmentType.NO_ASSIGNMENT`. Anything else
    (WHO_LEAST_DID_FIRST / RANDOM / IN_ALPHABETICAL_ORDER) gets its
    assignment recalculated by Grocy itself, so manual reassignment here
    would just get silently overwritten — see grocy_client.reassign()'s
    docstring.
    """
    assignment_type = getattr(raw_chore, "assignment_type", None)
    if AssignmentType is not None:
        return assignment_type == AssignmentType.NO_ASSIGNMENT
    # Fallback if the import above ever fails — string-match on the
    # enum's name so this degrades safely instead of raising.
    return str(getattr(assignment_type, "name", assignment_type)).upper() == (
        "NO_ASSIGNMENT"
    )


def _to_dashboard_chore(raw_chore) -> DashboardChore:
    """Translate a raw grocy-py Chore into our UI-facing DashboardChore.

    Field names below (`next_estimated_execution_time`,
    `next_execution_assigned_to_user_id`, `assignment_type`) match
    grocy-py's documented Chore model (see requirements doc §5/§7 and
    PLAN.md — confirmed against grocy-py's own reference docs, though not
    exercised against a live instance). If a live Grocy instance disagrees
    on a field name, this is the one place to fix it.
    """
    due_at = getattr(raw_chore, "next_estimated_execution_time", None)
    is_overdue = _is_overdue(due_at)

    return DashboardChore(
        id=raw_chore.id,
        name=raw_chore.name,
        description=getattr(raw_chore, "description", None),
        assigned_user_id=getattr(
            raw_chore, "next_execution_assigned_to_user_id", None
        ),
        due_at=due_at,
        is_overdue=is_overdue,
        is_manually_reassignable=_is_manually_reassignable(raw_chore),
    )


def _is_overdue(due_at: datetime | None) -> bool:
    if due_at is None:
        return False
    now = datetime.now(due_at.tzinfo) if due_at.tzinfo else datetime.now()
    return due_at < now


def _chore_sort_key(chore: DashboardChore):
    """Overdue chores first, then soonest-due first, undated chores last
    within each group — matches Grocy's own chores table ordering intent
    (requirements §5).

    Note: mixes `chore.due_at` with a naive `datetime.max` fallback —
    fine as long as Grocy's timestamps are consistently naive or
    consistently aware. If a live instance returns a mix of both within
    the same chore list, this raises a TypeError on comparison; verify
    against real data and normalize (e.g. via `_is_overdue`'s tzinfo
    handling) if that turns out to be the case.
    """
    return (
        0 if chore.is_overdue else 1,
        chore.due_at is None,
        chore.due_at or datetime.max,
    )


def _extract_execution_id(execute_result) -> int | None:
    """Best-effort extraction of an execution ID from grocy-py's
    execute() return value.

    TODO: confirm grocy-py's actual return type against a live instance
    (see grocy_client.mark_done()'s docstring) and replace this with a
    direct attribute/key access once known. Handles both an object with
    an `.id` attribute and a plain dict with an "id" key as placeholder
    guesses; falls back to None (no Undo action shown) if neither works,
    so this degrades safely rather than raising.
    """
    if execute_result is None:
        return None
    if hasattr(execute_result, "id"):
        try:
            return int(execute_result.id)
        except (TypeError, ValueError):
            return None
    if isinstance(execute_result, dict) and "id" in execute_result:
        try:
            return int(execute_result["id"])
        except (TypeError, ValueError):
            return None
    return None
