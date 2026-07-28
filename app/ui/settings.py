"""Settings page: edit the included-users list, their display order, and
per-user color overrides — i.e. everything in app/user_config.py.

This is the only page besides the dashboard itself. No auth in front of
it (see requirements §3 — no-login, trusted-LAN model applies here too),
so treat this as "anyone with physical/network access to the dashboard
can change who's on it," which is consistent with the rest of the app's
threat model.
"""

from __future__ import annotations

from nicegui import ui

from app.config import Config
from app.grocy_client import GrocyClient
from app.ui import theme
from app.ui.theme import (
    BACKGROUND,
    SURFACE,
    TEXT_PRIMARY,
    TEXT_MUTED,
    OVERDUE_ACCENT,
    ResolvedTheme,
    resolve_theme,
    color_swatch_picker,
    get_user_color,
)
from app.user_config import (
    UserConfig,
    UserConfigNotFoundError,
    UserEntry,
    load_user_config,
    save_user_config,
)


def build_settings_page(client: GrocyClient, config: Config) -> None:
    """Register the settings page. Call once from main.py."""

    @ui.page("/settings")
    def settings_page() -> None:
        ui.query("body").style(f"background: {theme.BACKGROUND};")
        ui.link("← Back to dashboard", "/").style(f"color: {theme.TEXT_MUTED};").classes(
            "text-sm"
        )
        ui.label("Settings").style(
            f"color: {theme.TEXT_PRIMARY}; font-family: {theme.FONT_DISPLAY};"
        ).classes("text-3xl")

        user_config: UserConfig = _load_or_init(config.user_config_path)
        all_grocy_users = {u.id: u for u in client.list_users()}

        # --- Global Theme section ---
        with ui.expansion("Global Theme", icon="palette").classes("w-full mt-4"):
            ui.label("Customize the dashboard's overall color scheme.").style(
                f"color: {theme.TEXT_MUTED};"
            ).classes("text-sm")

            theme_overrides = {
                "page_bg": (user_config.page_bg, BACKGROUND, "Page background"),
                "surface": (user_config.surface, SURFACE, "Card default background"),
                "text_primary": (user_config.text_primary, TEXT_PRIMARY, "Primary text"),
                "text_muted": (user_config.text_muted, TEXT_MUTED, "Muted text"),
                "overdue_accent": (user_config.overdue_accent, OVERDUE_ACCENT, "Overdue accent"),
            }

            for field_name, (current_val, default_val, label) in theme_overrides.items():
                resolved_val = current_val or default_val
                with ui.row().classes("items-center gap-2 w-full"):
                    ui.label(label).style(f"color: {theme.TEXT_PRIMARY};").classes("w-40")
                    color_swatch_picker(
                        current_color=resolved_val,
                        on_select=lambda c, f=field_name: (
                            setattr(user_config, f, c),
                            render_entries(),
                        ),
                    )
                    if current_val is not None:
                        ui.button("Default", on_click=lambda f=field_name: (
                            setattr(user_config, f, None),
                            render_entries(),
                        )).props("flat dense")

            with ui.row().classes("items-center gap-2 mt-2"):
                ui.button("Reset all to defaults", on_click=lambda: (
                    setattr(user_config, "page_bg", None),
                    setattr(user_config, "surface", None),
                    setattr(user_config, "text_primary", None),
                    setattr(user_config, "text_muted", None),
                    setattr(user_config, "overdue_accent", None),
                    render_entries(),
                )).props("flat")

        ui.label("Users on the dashboard").style(f"color: {theme.TEXT_PRIMARY};").classes(
            "text-lg font-semibold mt-4"
        )
        entries_column = ui.column().classes("w-full gap-2")

        def render_entries() -> None:
            entries_column.clear()
            with entries_column:
                if not user_config.users:
                    ui.label("Nobody's added yet — add someone below.").style(
                        f"color: {theme.TEXT_MUTED};"
                    )
                for i, entry in enumerate(user_config.users):
                    _render_entry_row(entry, index=i, total=len(user_config.users))

        def _render_entry_row(entry: UserEntry, *, index: int, total: int) -> None:
            grocy_user = all_grocy_users.get(entry.id)
            display_name = (
                grocy_user.display_name if grocy_user else f"Unknown user #{entry.id}"
            )
            resolved_color = theme.get_user_color(entry.id, override=entry.color)

            def move(delta: int) -> None:
                new_index = index + delta
                user_config.users[index], user_config.users[new_index] = (
                    user_config.users[new_index],
                    user_config.users[index],
                )
                render_entries()

            def _set_accent(color: str | None) -> None:
                entry.color = color or None
                render_entries()

            def _set_card_bg(color: str | None) -> None:
                entry.card_bg = color or None
                render_entries()

            def confirm_remove() -> None:
                with ui.dialog() as dialog, ui.card():
                    ui.label(f'Remove "{display_name}" from the dashboard?')
                    ui.label(
                        "This only removes their card here — it doesn't "
                        "change anything in Grocy itself."
                    ).classes("text-sm")
                    with ui.row().classes("justify-end w-full gap-2"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")

                        def _do_remove() -> None:
                            user_config.users.remove(entry)
                            dialog.close()
                            render_entries()

                        ui.button("Remove", on_click=_do_remove).props(
                            "unelevated color=negative"
                        )
                dialog.open()

            with ui.row().classes("items-center gap-2 w-full"):
                ui.button(icon="arrow_upward", on_click=lambda: move(-1)).props(
                    "flat dense"
                ).set_enabled(index > 0)
                ui.button(icon="arrow_downward", on_click=lambda: move(1)).props(
                    "flat dense"
                ).set_enabled(index < total - 1)

                ui.label(display_name).style(f"color: {theme.TEXT_PRIMARY};").classes(
                    "flex-grow font-medium"
                )

                color_swatch_picker(
                    current_color=entry.color or resolved_color,
                    on_select=_set_accent,
                )
                if entry.color is not None:
                    ui.button("Use default", on_click=lambda: _set_accent(None)).props(
                        "flat dense"
                    )

                ui.label("BG").style(f"color: {theme.TEXT_MUTED};").classes("text-xs")
                color_swatch_picker(
                    current_color=entry.card_bg or SURFACE,
                    on_select=_set_card_bg,
                )
                if entry.card_bg is not None:
                    ui.button("Use default", on_click=lambda: _set_card_bg(None)).props(
                        "flat dense"
                    )

                ui.button(icon="delete", on_click=confirm_remove).props(
                    "flat dense color=negative"
                )

        render_entries()

        ui.label("Add a user").style(f"color: {theme.TEXT_PRIMARY};").classes(
            "text-lg font-semibold mt-6"
        )
        with ui.row().classes("items-center gap-2"):
            add_user_select = ui.select(
                {uid: u.display_name for uid, u in all_grocy_users.items()},
                label="Grocy user",
            ).classes("w-64")

            def add_user() -> None:
                if add_user_select.value is None:
                    ui.notify("Pick a user first", type="warning")
                    return
                if add_user_select.value in {e.id for e in user_config.users}:
                    ui.notify("That user is already on the dashboard", type="warning")
                    return
                user_config.users.append(UserEntry(id=add_user_select.value, color=None))
                add_user_select.set_value(None)
                render_entries()

            ui.button("Add", on_click=add_user)

        def save() -> None:
            save_user_config(config.user_config_path, user_config)
            ui.notify("Saved. Changes apply on the dashboard's next refresh.")

        ui.button("Save changes", on_click=save).props(
            "unelevated color=primary"
        ).classes("mt-6")


def _load_or_init(path: str) -> UserConfig:
    """Load the user config, starting from an empty one on first run
    (no file yet) rather than crashing — this page's whole job is to let
    someone create that file for the first time."""
    try:
        return load_user_config(path)
    except UserConfigNotFoundError:
        return UserConfig(users=[])
