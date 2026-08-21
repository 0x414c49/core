"""Test the Zaptec update platform."""

from typing import Any
from unittest.mock import MagicMock

from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_TITLE,
    SERVICE_INSTALL,
    UpdateEntityFeature,
)
from homeassistant.components.update.const import ATTR_IN_PROGRESS
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration
from .const import (
    CHARGER_ID,
    CHARGER_INFO,
    FIRMWARE_UPDATE_AVAILABLE,
    INSTALLATION_ID,
    UPDATE_FIRMWARE_UNIQUE_ID,
)

from tests.common import MockConfigEntry


def _firmware_update_entity_id(hass: HomeAssistant) -> str:
    """Resolve the firmware update entity id from the registry."""
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "update", "zaptec", UPDATE_FIRMWARE_UNIQUE_ID
    )
    assert entity_id is not None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is None
    return entity_id


async def test_firmware_up_to_date(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the firmware entity when the charger is up to date."""
    await setup_integration(hass, mock_config_entry)

    entity_id = _firmware_update_entity_id(hass)
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2.1.1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2.1.1"
    assert state.attributes[ATTR_TITLE] == "Firmware"
    assert not state.attributes.get(ATTR_IN_PROGRESS, False)
    assert not state.attributes.get(ATTR_SUPPORTED_FEATURES, 0) & (
        UpdateEntityFeature.INSTALL
    )


async def test_firmware_install(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, Any],
) -> None:
    """Test starting a firmware upgrade when an update is available."""
    zaptec_get_responses[f"chargerFirmware/installation/{INSTALLATION_ID}"] = (
        FIRMWARE_UPDATE_AVAILABLE
    )

    await setup_integration(hass, mock_config_entry)

    entity_id = _firmware_update_entity_id(hass)
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2.1.1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2.2.0"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] & UpdateEntityFeature.INSTALL

    await hass.services.async_call(
        "update",
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_zaptec.async_post.assert_called_once_with(
        f"chargers/{CHARGER_ID}/sendCommand/200"
    )


async def test_firmware_ignores_older_available_version(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, Any],
) -> None:
    """Test older available versions are not exposed as updates."""
    zaptec_get_responses[f"chargerFirmware/installation/{INSTALLATION_ID}"] = [
        {
            "chargerId": CHARGER_ID,
            "deviceId": "ZAP123456",
            "isOnline": True,
            "currentVersion": "3.3.3.1",
            "availableVersion": "2.4.2.4",
            "isUpToDate": False,
            "deviceType": 1,
        }
    ]

    await setup_integration(hass, mock_config_entry)

    entity_id = _firmware_update_entity_id(hass)
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_INSTALLED_VERSION] == "3.3.3.1"
    assert state.attributes[ATTR_LATEST_VERSION] == "3.3.3.1"
    assert not state.attributes[ATTR_SUPPORTED_FEATURES] & UpdateEntityFeature.INSTALL


async def test_firmware_update_not_created_without_write_role(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, Any],
) -> None:
    """Test firmware update entity is not created for accounts with User access only."""
    zaptec_get_responses[f"chargers?InstallationId={INSTALLATION_ID}"] = {
        "data": [{**CHARGER_INFO, "currentUserRoles": 1}]
    }
    zaptec_get_responses[f"chargerFirmware/installation/{INSTALLATION_ID}"] = (
        FIRMWARE_UPDATE_AVAILABLE
    )

    await setup_integration(hass, mock_config_entry)

    entity_registry = er.async_get(hass)
    assert (
        entity_registry.async_get_entity_id(
            "update", "zaptec", UPDATE_FIRMWARE_UNIQUE_ID
        )
        is None
    )
