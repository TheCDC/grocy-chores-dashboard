"""Entrypoint. Run with: python -m app.main (or via the Dockerfile CMD)."""

from __future__ import annotations

from nicegui import ui

from app.config import load_config
from app.grocy_client import GrocyClient
from app.services.chore_service import ChoreService
from app.ui.dashboard import build_dashboard_page
from app.ui.settings import build_settings_page


def main() -> None:
    config = load_config()
    client = GrocyClient.from_config(config)
    chore_service = ChoreService(client, config)

    build_dashboard_page(chore_service, config.refresh_interval_seconds)
    build_settings_page(client, config)

    ui.run(
        host="0.0.0.0",
        port=config.dashboard_port,
        title="Chores Dashboard",
        reload=config.dev_reload,
        # TODO: consider ui.run(..., show=False) in the container context
        # (no local browser to open), and dark/light theming decisions
        # once ui/theme.py's real values are picked.
    )


# NiceGUI's recommended entrypoint guard — required for its reload/
# multiprocessing behavior to work correctly.
if __name__ in {"__main__", "__mp_main__"}:
    main()
