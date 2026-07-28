"""Tests for chore_service color config integration."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import Config
from app.grocy_client import GrocyClient
from app.models import DashboardUser
from app.services.chore_service import ChoreService
from app.ui.theme import ResolvedTheme, SURFACE
from app.user_config import UserConfig, UserEntry


@pytest.fixture
def service():
    config = MagicMock(spec=Config)
    config.user_config_path = "/dev/null/nonexistent"
    client = MagicMock(spec=GrocyClient)
    return ChoreService(client, config)


def test_get_dashboard_data_returns_resolved_theme(service):
    """get_dashboard_data() should return a (list, ResolvedTheme) tuple."""
    # Force _load_user_config to return a config with overrides
    service._load_user_config = lambda: UserConfig(
        users=[UserEntry(id=1)],
        page_bg="#000000",
    )
    service._client.list_users.return_value = [
        MagicMock(id=1, display_name="Alice")
    ]
    service._client.list_chores.return_value = []

    result = service.get_dashboard_data()

    assert isinstance(result, tuple), "Should return a tuple"
    assert len(result) == 2
    user_chores_list, theme = result
    assert isinstance(theme, ResolvedTheme)
    assert theme.background == "#000000"


def test_dashboard_user_has_resolved_card_bg(service):
    service._load_user_config = lambda: UserConfig(
        users=[UserEntry(id=1, card_bg="#111111")],
    )
    service._client.list_users.return_value = [
        MagicMock(id=1, display_name="Alice")
    ]
    service._client.list_chores.return_value = []

    user_chores_list, _ = service.get_dashboard_data()
    assert len(user_chores_list) == 1
    assert user_chores_list[0].user.card_bg == "#111111"


def test_dashboard_user_card_bg_falls_back_to_surface(service):
    service._load_user_config = lambda: UserConfig(
        users=[UserEntry(id=1)],  # no card_bg override
    )
    service._client.list_users.return_value = [
        MagicMock(id=1, display_name="Alice")
    ]
    service._client.list_chores.return_value = []

    user_chores_list, theme = service.get_dashboard_data()
    assert user_chores_list[0].user.card_bg == SURFACE
