"""Tests for theme resolution."""
from __future__ import annotations

import pytest

from app.ui.theme import BACKGROUND, SURFACE, TEXT_PRIMARY, TEXT_MUTED, OVERDUE_ACCENT
from app.ui.theme import ResolvedTheme, resolve_theme
from app.user_config import UserConfig, UserEntry


def test_resolve_theme_uses_defaults_when_no_overrides():
    theme = resolve_theme(None)
    assert theme.background == BACKGROUND
    assert theme.surface == SURFACE
    assert theme.text_primary == TEXT_PRIMARY
    assert theme.text_muted == TEXT_MUTED
    assert theme.overdue_accent == OVERDUE_ACCENT


def test_resolve_theme_uses_defaults_when_all_none():
    config = UserConfig(users=[])
    theme = resolve_theme(config)
    assert theme.background == BACKGROUND
    assert theme.surface == SURFACE


def test_resolve_theme_applies_partial_overrides():
    config = UserConfig(users=[UserEntry(id=1)], page_bg="#000000", surface="#111111")
    theme = resolve_theme(config)
    assert theme.background == "#000000"
    assert theme.surface == "#111111"
    assert theme.text_primary == TEXT_PRIMARY  # not overridden
    assert theme.text_muted == TEXT_MUTED
    assert theme.overdue_accent == OVERDUE_ACCENT


def test_resolve_theme_applies_all_overrides():
    config = UserConfig(
        users=[UserEntry(id=1)],
        page_bg="#a", surface="#b", text_primary="#c",
        text_muted="#d", overdue_accent="#e",
    )
    theme = resolve_theme(config)
    assert theme.background == "#a"
    assert theme.surface == "#b"
    assert theme.text_primary == "#c"
    assert theme.text_muted == "#d"
    assert theme.overdue_accent == "#e"


def test_resolved_theme_fields_are_strings():
    theme = resolve_theme()
    assert isinstance(theme.background, str)
    assert isinstance(theme.surface, str)
    assert isinstance(theme.text_primary, str)
    assert isinstance(theme.text_muted, str)
    assert isinstance(theme.overdue_accent, str)
