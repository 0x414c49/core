"""Test the Zaptec binary sensor platform."""

from unittest.mock import MagicMock

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import setup_integration
from .const import (
    BINARY_SENSOR_AUTHORIZATION_REQUIRED,
    BINARY_SENSOR_CAR_CONNECTED,
    BINARY_SENSOR_CHARGING,
    BINARY_SENSOR_ONLINE,
    BINARY_SENSOR_PROBLEM,
)

from tests.common import MockConfigEntry


async def test_binary_sensors(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test charger binary sensors while charging."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(BINARY_SENSOR_CHARGING).state == STATE_ON
    assert hass.states.get(BINARY_SENSOR_CAR_CONNECTED).state == STATE_ON
    assert hass.states.get(BINARY_SENSOR_ONLINE).state == STATE_ON
    assert hass.states.get(BINARY_SENSOR_PROBLEM).state == STATE_OFF
    assert hass.states.get(BINARY_SENSOR_AUTHORIZATION_REQUIRED).state == STATE_ON
