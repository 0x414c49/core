"""Test the Zaptec integration init."""

from unittest.mock import MagicMock

from homeassistant.components.zaptec import async_remove_config_entry_device
from homeassistant.components.zaptec.api import (
    ZaptecApiError,
    ZaptecAuthError,
    ZaptecConnectionError,
)
from homeassistant.components.zaptec.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from .conftest import setup_integration
from .const import (
    BINARY_SENSOR_DRIVEWAY_CHARGING,
    BUTTON_DRIVEWAY_STOP_CHARGING,
    CHARGER_2_ID,
    CHARGER_2_INFO,
    CHARGER_ID,
    CHARGER_INFO,
    CHARGING_STATES,
    INSTALLATION_ID,
    NUMBER_DRIVEWAY_MAX_CHARGE_CURRENT,
    SENSOR_DRIVEWAY_TOTAL_CHARGE_POWER,
    SWITCH_DRIVEWAY_CHARGING,
    UPDATE_DRIVEWAY_FIRMWARE,
)

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_setup_entry."""
    entry = await setup_integration(hass, mock_config_entry)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None

    device_entries = dr.async_get(hass).devices
    device_identifiers = {
        identifier
        for device in device_entries.values()
        if mock_config_entry.entry_id in device.config_entries
        for identifier in device.identifiers
    }
    assert device_identifiers == {
        (DOMAIN, "inst-1"),
        (DOMAIN, "chg-1"),
        (DOMAIN, "apm-1"),
    }

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_async_setup_auth_failed(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails when the first refresh raises an auth error."""
    mock_zaptec.async_get.side_effect = ZaptecAuthError("Invalid token")

    entry = await setup_integration(hass, mock_config_entry)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(
        flow["context"].get("source") == "reauth"
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN
    )


async def test_async_setup_connection_error(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when authentication cannot connect."""
    mock_zaptec.async_get_access_token.side_effect = ZaptecConnectionError(
        "Error connecting to Zaptec API"
    )

    entry = await setup_integration(hass, mock_config_entry)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_state_connection_error(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, object],
) -> None:
    """Test normal charger state failures retry setup."""
    zaptec_get_responses[f"chargers/{CHARGER_ID}/state"] = ZaptecApiError(
        "Zaptec API GET state failed: 500"
    )

    entry = await setup_integration(hass, mock_config_entry)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_loads_when_firmware_fails(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, object],
) -> None:
    """Test optional firmware data does not block setup."""
    zaptec_get_responses[f"chargerFirmware/installation/{INSTALLATION_ID}"] = (
        ZaptecApiError("Zaptec API GET firmware failed: 500")
    )

    entry = await setup_integration(hass, mock_config_entry)

    assert entry.state is ConfigEntryState.LOADED


async def test_new_charger_entities_are_added_after_refresh(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, object],
) -> None:
    """Test a new charger is added without reloading the integration."""
    entry = await setup_integration(hass, mock_config_entry)

    zaptec_get_responses[f"chargers?InstallationId={INSTALLATION_ID}"] = {
        "data": [CHARGER_INFO, CHARGER_2_INFO]
    }
    zaptec_get_responses[f"chargers/{CHARGER_2_ID}"] = CHARGER_2_INFO
    zaptec_get_responses[f"chargers/{CHARGER_2_ID}/state"] = CHARGING_STATES
    await entry.runtime_data.coordinator.async_request_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(SENSOR_DRIVEWAY_TOTAL_CHARGE_POWER)
    assert hass.states.get(BINARY_SENSOR_DRIVEWAY_CHARGING)
    assert hass.states.get(SWITCH_DRIVEWAY_CHARGING)
    assert hass.states.get(BUTTON_DRIVEWAY_STOP_CHARGING)
    assert hass.states.get(UPDATE_DRIVEWAY_FIRMWARE)

    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(NUMBER_DRIVEWAY_MAX_CHARGE_CURRENT)


async def test_remove_config_entry_device_keeps_current_device(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test current Zaptec devices cannot be removed from the config entry."""
    entry = await setup_integration(hass, mock_config_entry)
    dev_reg = dr.async_get(hass)
    device_entry = dev_reg.async_get_device_by_identifier(
        (DOMAIN, CHARGER_ID), entry.entry_id
    )

    assert device_entry is not None
    assert not await async_remove_config_entry_device(hass, entry, device_entry)


async def test_remove_config_entry_device_removes_stale_device(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stale Zaptec devices can be removed from the config entry."""
    entry = await setup_integration(hass, mock_config_entry)
    dev_reg = dr.async_get(hass)
    device_entry = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "stale-device")},
    )

    assert await async_remove_config_entry_device(hass, entry, device_entry)


def _charger_warning_issue_id(entry: MockConfigEntry) -> str:
    """Return the warning issue id for the default charger."""
    return f"charger_warning_{entry.entry_id}_{CHARGER_ID}"


async def test_charger_warning_creates_repair_issue_from_info(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, object],
) -> None:
    """Test charger warnings create a repair issue."""
    charger_info = dict(CHARGER_INFO, warnings=["OverCurrent"])
    zaptec_get_responses[f"chargers?InstallationId={INSTALLATION_ID}"] = {
        "data": [charger_info]
    }

    entry = await setup_integration(hass, mock_config_entry)

    issue = issue_registry.async_get_issue(DOMAIN, _charger_warning_issue_id(entry))
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.is_fixable is False
    assert issue.is_persistent is False
    assert issue.translation_key == "charger_warning"


async def test_charger_warning_creates_repair_issue_from_observation(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, object],
) -> None:
    """Test charger warning flags create a repair issue."""
    zaptec_get_responses[f"chargers/{CHARGER_ID}/state"] = [
        dict(state, valueAsString="1") if state["stateId"] == 804 else dict(state)
        for state in CHARGING_STATES
    ]

    entry = await setup_integration(hass, mock_config_entry)

    assert issue_registry.async_get_issue(DOMAIN, _charger_warning_issue_id(entry))


async def test_charger_warning_repair_issue_clears(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, object],
) -> None:
    """Test charger warning repair issues clear when the warning clears."""
    zaptec_get_responses[f"chargers?InstallationId={INSTALLATION_ID}"] = {
        "data": [dict(CHARGER_INFO, warnings=["OverCurrent"])]
    }
    entry = await setup_integration(hass, mock_config_entry)
    issue_id = _charger_warning_issue_id(entry)
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    zaptec_get_responses[f"chargers?InstallationId={INSTALLATION_ID}"] = {
        "data": [dict(CHARGER_INFO, warnings=None)]
    }
    await entry.runtime_data.coordinator.async_request_refresh()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_charger_warning_repair_issue_clears_on_unload(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, object],
) -> None:
    """Test charger warning repair issues clear when the entry unloads."""
    zaptec_get_responses[f"chargers?InstallationId={INSTALLATION_ID}"] = {
        "data": [dict(CHARGER_INFO, warnings=["OverCurrent"])]
    }
    entry = await setup_integration(hass, mock_config_entry)
    issue_id = _charger_warning_issue_id(entry)
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
