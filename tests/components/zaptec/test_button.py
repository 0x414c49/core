"""Test the Zaptec button platform."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import setup_integration
from .const import (
    BUTTON_DEAUTHORIZE_AND_STOP,
    BUTTON_RESTART_CHARGER,
    BUTTON_RESUME_CHARGING,
    BUTTON_STOP_CHARGING,
    CHARGER_ID,
    CHARGER_INFO,
    INSTALLATION_ID,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("entity_id", "command_id"),
    [
        pytest.param(BUTTON_RESUME_CHARGING, 507, id="resume_charging"),
        pytest.param(BUTTON_STOP_CHARGING, 506, id="stop_charging"),
        pytest.param(BUTTON_DEAUTHORIZE_AND_STOP, 10001, id="deauthorize_and_stop"),
        pytest.param(BUTTON_RESTART_CHARGER, 102, id="restart_charger"),
    ],
)
async def test_button_press(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    command_id: int,
) -> None:
    """Test pressing a button sends the mapped charger command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_zaptec.async_post.assert_called_once_with(
        f"chargers/{CHARGER_ID}/sendCommand/{command_id}"
    )


async def test_buttons_not_created_without_write_role(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, Any],
) -> None:
    """Test command buttons are not created for accounts with User access only."""
    zaptec_get_responses[f"chargers?InstallationId={INSTALLATION_ID}"] = {
        "data": [{**CHARGER_INFO, "currentUserRoles": 1}]
    }

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(BUTTON_RESUME_CHARGING) is None
    assert hass.states.get(BUTTON_STOP_CHARGING) is None
    assert hass.states.get(BUTTON_DEAUTHORIZE_AND_STOP) is None
    assert hass.states.get(BUTTON_RESTART_CHARGER) is None
