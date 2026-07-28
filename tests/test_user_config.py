"""Tests for user_config.py new color fields."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.user_config import (
    UserConfig,
    UserEntry,
    load_user_config,
    save_user_config,
)


def test_user_entry_card_bg_defaults_to_none():
    entry = UserEntry(id=1)
    assert entry.card_bg is None


def test_user_entry_card_bg_can_be_set():
    entry = UserEntry(id=1, card_bg="#111111")
    assert entry.card_bg == "#111111"


def test_user_entry_text_color_defaults_to_none():
    entry = UserEntry(id=1)
    assert entry.text_color is None


def test_user_entry_text_color_can_be_set():
    entry = UserEntry(id=1, text_color="#ABCDEF")
    assert entry.text_color == "#ABCDEF"


def test_user_entry_text_muted_defaults_to_none():
    entry = UserEntry(id=1)
    assert entry.text_muted is None


def test_user_entry_text_muted_can_be_set():
    entry = UserEntry(id=1, text_muted="#654321")
    assert entry.text_muted == "#654321"


def test_user_config_global_overrides_default_to_none():
    config = UserConfig(users=[UserEntry(id=1)])
    assert config.page_bg is None
    assert config.surface is None
    assert config.text_primary is None
    assert config.text_muted is None
    assert config.overdue_accent is None


def test_user_config_global_overrides_round_trip(tmp_path: Path):
    """Save a config with global overrides and load it back."""
    path = tmp_path / "test.json"
    original = UserConfig(
        users=[UserEntry(id=2, color="#FF0000", card_bg="#111111")],
        page_bg="#123456",
        surface="#654321",
    )
    save_user_config(path, original)
    loaded = load_user_config(path)
    assert loaded.page_bg == "#123456"
    assert loaded.surface == "#654321"
    assert loaded.text_primary is None
    assert loaded.users[0].card_bg == "#111111"
    assert loaded.users[0].color == "#FF0000"
    assert loaded.users[0].text_color is None
    assert loaded.users[0].text_muted is None


def test_load_user_config_missing_new_fields_are_none(tmp_path: Path):
    """Old config files without card_bg / global fields should load with None defaults."""
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"users": [{"id": 1, "color": "#FFD166"}]}))
    config = load_user_config(path)
    assert config.users[0].card_bg is None
    assert config.users[0].text_color is None
    assert config.users[0].text_muted is None
    assert config.page_bg is None
