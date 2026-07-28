"""Application configuration, loaded entirely from environment variables.

Kept dependency-free (no pydantic etc.) so this module can be imported and
unit tested with nothing else running.

Note: the *included users* list (formerly DASHBOARD_USER_IDS) has moved to
a mutable JSON file — see app/user_config.py. This module only holds the
*path* to that file. Static/deploy-time settings (Grocy connection, port,
refresh interval) stay here since they aren't meant to be editable from
the settings page.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    # --- Grocy connection ---
    grocy_base_url: str
    grocy_api_key: str
    grocy_port: int | None = None
    grocy_path: str | None = None
    grocy_verify_ssl: bool = True

    # --- Dashboard behavior ---
    # Path to the JSON file holding the included-users list + per-user
    # color overrides (app/user_config.py). Mount this as a volume in
    # docker-compose.yml so edits made via the settings page persist
    # across container restarts.
    user_config_path: str = "/data/dashboard_users.json"
    refresh_interval_seconds: int = 30
    dashboard_port: int = 8080

    # --- Development ---
    # Enable NiceGUI's file-watching reload for live code changes.
    dev_reload: bool = False


def _get_required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def load_config() -> Config:
    """Load and validate configuration from environment variables.

    Raises:
        ConfigError: if required variables are missing or malformed.
    """
    grocy_base_url = _get_required("GROCY_BASE_URL")
    grocy_api_key = _get_required("GROCY_API_KEY")

    grocy_port_raw = os.environ.get("GROCY_PORT")
    grocy_port = int(grocy_port_raw) if grocy_port_raw else None

    grocy_verify_ssl = os.environ.get("GROCY_VERIFY_SSL", "true").lower() not in (
        "false",
        "0",
        "no",
    )

    user_config_path = os.environ.get(
        "USER_CONFIG_PATH", "/data/dashboard_users.json"
    )

    refresh_interval_seconds = int(
        os.environ.get("REFRESH_INTERVAL_SECONDS", "30")
    )
    dashboard_port = int(os.environ.get("DASHBOARD_PORT", "8080"))

    dev_reload = os.environ.get("DEV_RELOAD", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    return Config(
        grocy_base_url=grocy_base_url,
        grocy_api_key=grocy_api_key,
        grocy_port=grocy_port,
        grocy_path=os.environ.get("GROCY_PATH"),
        grocy_verify_ssl=grocy_verify_ssl,
        user_config_path=user_config_path,
        refresh_interval_seconds=refresh_interval_seconds,
        dashboard_port=dashboard_port,
        dev_reload=dev_reload,
    )
