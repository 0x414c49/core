"""Test the Zaptec switch platform."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import setup_integration
from .const import (
    CHARGER_ID,
    CHARGER_INFO_DISCONNECTED,
    CHARGER_INFO_PAUSED,
    DISCONNECTED_STATES,
    INSTALLATION_ID,
    PAUSED_STATES,
    SWITCH_CHARGING,
    SWITCH_PERMANENT_CABLE_LOCK,
)

from tests.common import MockConfigEntry


async def test_switch_state(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the charging switch is on while charging."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(SWITCH_CHARGING)
    assert state
    assert state.state == STATE_ON


async def test_switch_turn_off(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pausing charging sends the final stop command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "switch",
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SWITCH_CHARGING},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_zaptec.async_post.assert_called_once_with(
        f"chargers/{CHARGER_ID}/sendCommand/506"
    )


async def test_permanent_cable_lock_switch(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the permanent cable lock posts local settings."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(SWITCH_PERMANENT_CABLE_LOCK)
    assert state
    assert state.state == STATE_OFF

    await hass.services.async_call(
        "switch",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SWITCH_PERMANENT_CABLE_LOCK},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_zaptec.async_post.assert_called_once_with(
        f"chargers/{CHARGER_ID}/localSettings",
        {"Cable": {"PermanentLock": True}},
    )
    state = hass.states.get(SWITCH_PERMANENT_CABLE_LOCK)
    assert state
    assert state.state == STATE_ON


async def test_switch_turn_on_when_paused(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, Any],
) -> None:
    """Test resuming charging when charging was paused."""
    zaptec_get_responses[f"chargers?InstallationId={INSTALLATION_ID}"] = {
        "data": [CHARGER_INFO_PAUSED]
    }
    zaptec_get_responses[f"chargers/{CHARGER_ID}/state"] = PAUSED_STATES

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(SWITCH_CHARGING)
    assert state
    assert state.state == STATE_OFF

    await hass.services.async_call(
        "switch",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SWITCH_CHARGING},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_zaptec.async_post.assert_called_once_with(
        f"chargers/{CHARGER_ID}/sendCommand/507"
    )


async def test_switch_turn_on_not_paused(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test resuming charging fails when it was not paused."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_CHARGING},
            blocking=True,
        )

    mock_zaptec.async_post.assert_not_called()


async def test_switch_unavailable_when_disconnected(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, Any],
) -> None:
    """Test the switch is unavailable when no vehicle is connected."""
    zaptec_get_responses[f"chargers?InstallationId={INSTALLATION_ID}"] = {
        "data": [CHARGER_INFO_DISCONNECTED]
    }
    zaptec_get_responses[f"chargers/{CHARGER_ID}/state"] = DISCONNECTED_STATES

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(SWITCH_CHARGING)
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_switch_not_created_without_write_role(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, Any],
) -> None:
    """Test charging switch is not created for accounts with User access only."""
    zaptec_get_responses[f"chargers?InstallationId={INSTALLATION_ID}"] = {
        "data": [{**CHARGER_INFO_PAUSED, "currentUserRoles": 1}]
    }

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(SWITCH_CHARGING) is None
    assert hass.states.get(SWITCH_PERMANENT_CABLE_LOCK) is None
