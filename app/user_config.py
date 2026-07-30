"""User config: the list of included Grocy users, display order, and
per-user color overrides — stored as a JSON file rather than an env var
so it can be edited at runtime from the settings page (see
app/ui/settings.py) without restarting the container.

This is intentionally separate from app/config.py (Config), which stays
env-var-driven and read-only at process start (Grocy connection details,
port, refresh interval — things that genuinely are deploy-time config,
not something a family member should be able to change from a touchscreen).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


class UserConfigError(RuntimeError):
    """Raised on malformed or unreadable user config."""


class UserConfigNotFoundError(UserConfigError):
    """Raised specifically when the config file doesn't exist yet — e.g.
    first run before anyone has visited /settings. Callers (ChoreService,
    the settings page) can catch this specifically to start from an empty
    UserConfig instead of treating it as a real error, while still
    surfacing malformed-JSON as a hard failure via the base
    UserConfigError.
    """


@dataclass
class UserEntry:
    id: int
    # Explicit color override, e.g. "#3B82F6". If None, the color is
    # derived deterministically from `id` — see ui/theme.get_user_color().
    # This field is what the settings page writes to when someone picks
    # a custom color for a user.
    color: str | None = None
    nickname: str | None = None
    card_bg: str | None = None
    text_color: str | None = None
    text_muted: str | None = None


@dataclass
class UserConfig:
    # Order of this list is the dashboard's left-to-right card order.
    users: list[UserEntry] = field(default_factory=list)
    page_bg: str | None = None
    surface: str | None = None
    text_primary: str | None = None
    text_muted: str | None = None
    overdue_accent: str | None = None

    def user_ids(self) -> list[int]:
        return [u.id for u in self.users]

    def color_for(self, user_id: int) -> str | None:
        for u in self.users:
            if u.id == user_id:
                return u.color
        return None


def load_user_config(path: str | Path) -> UserConfig:
    """Load the user config JSON.

    Raises:
        UserConfigNotFoundError: if the file doesn't exist (first run —
            callers may want to fall back to an empty UserConfig instead
            of treating this as fatal; see chore_service.py / settings.py).
        UserConfigError: if the file exists but is malformed — a real
            problem, not a first-run state, so this is not caught/hidden
            anywhere in the app.
    """
    p = Path(path)
    if not p.exists():
        raise UserConfigNotFoundError(
            f"User config file not found: {p}. See "
            "config/dashboard_users.example.json for the expected format, "
            "or add users from the settings page (/settings) to create it."
        )
    try:
        raw = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise UserConfigError(f"Invalid JSON in {p}: {exc}") from exc

    try:
        users = [UserEntry(id=u["id"], color=u.get("color"), nickname=u.get("nickname"), card_bg=u.get("card_bg"), text_color=u.get("text_color"), text_muted=u.get("text_muted")) for u in raw["users"]]
    except (KeyError, TypeError) as exc:
        raise UserConfigError(
            f"Malformed user config in {p}: expected {{'users': [{{'id': int, "
            f"'color': str|null, 'card_bg': str|null, 'text_color': str|null, 'text_muted': str|null}}, ...]}}"
        ) from exc

    if not users:
        raise UserConfigError(f"User config in {p} has no users listed")

    return UserConfig(
        users=users,
        page_bg=raw.get("page_bg"),
        surface=raw.get("surface"),
        text_primary=raw.get("text_primary"),
        text_muted=raw.get("text_muted"),
        overdue_accent=raw.get("overdue_accent"),
    )


def save_user_config(path: str | Path, config: UserConfig) -> None:
    """Persist the user config JSON. Called from the settings page on save.

    TODO: this is a plain overwrite with no file locking — fine for a
    single-container/single-editor home deployment, but note the
    assumption if this ever runs with multiple replicas.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {}
    payload["page_bg"] = config.page_bg
    payload["surface"] = config.surface
    payload["text_primary"] = config.text_primary
    payload["text_muted"] = config.text_muted
    payload["overdue_accent"] = config.overdue_accent
    payload["users"] = [asdict(u) for u in config.users]
    p.write_text(json.dumps(payload, indent=2) + "\n")
