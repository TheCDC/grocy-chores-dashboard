"""UI-facing data models.

The `ui/` package should only ever import these — never grocy-py's raw
response objects directly — so grocy-py version changes stay contained to
`services/chore_service.py`'s translation layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DashboardUser:
    id: int
    display_name: str
    # Resolved via ui.theme.get_user_color(id, override=<user_config color>)
    # in chore_service.py — deterministic from user id unless overridden
    # in the user config JSON (see app/user_config.py, settings page).
    color: str
    card_bg: str = ""
    text_color: str = ""
    text_muted: str = ""


@dataclass(frozen=True)
class DashboardChore:
    id: int
    name: str
    description: str | None
    assigned_user_id: int | None
    due_at: datetime | None
    is_overdue: bool
    # Whether this chore's assignment can safely be changed via reassign()
    # without Grocy's own assignment logic silently overwriting it.
    # See grocy_client.reassign()'s docstring — set this from
    # chore.assignment_type == AssignmentType.NO_ASSIGNMENT once that
    # open question is resolved.
    is_manually_reassignable: bool


@dataclass(frozen=True)
class UserChores:
    """One user's card worth of data: who they are + their sorted chores."""

    user: DashboardUser
    chores: list[DashboardChore]
