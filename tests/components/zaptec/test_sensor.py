"""Test the Zaptec sensor platform."""

from unittest.mock import MagicMock

from homeassistant.components.zaptec.const import DOMAIN
from homeassistant.components.zaptec.coordinator import HIERARCHY_REFRESH_CYCLES
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import setup_integration
from .const import (
    APM_ID,
    APM_STATES,
    CHARGER_ID,
    CHARGER_INFO,
    CHARGING_STATES,
    HIERARCHY_WITH_NEW_APM,
    INSTALLATION_ID,
    SENSOR_CHARGE_CURRENT_SET,
    SENSOR_CHARGE_DURATION,
    SENSOR_CHARGER_MODE,
    SENSOR_CURRENT_PHASE1,
    SENSOR_HUMIDITY,
    SENSOR_INSTALLATION_ACTIVE_CHARGERS,
    SENSOR_INSTALLATION_AVAILABLE_CURRENT,
    SENSOR_LIFETIME_ENERGY,
    SENSOR_SENSE_2_ACTIVE_POWER,
    SENSOR_SENSE_ACTIVE_POWER,
    SENSOR_SENSE_ENERGY_EXPORTED,
    SENSOR_SENSE_ENERGY_IMPORTED,
    SENSOR_SESSION_ENERGY,
    SENSOR_TAMPER,
    SENSOR_TEMPERATURE_INTERNAL,
    SENSOR_TOTAL_CHARGE_POWER,
    SENSOR_VOLTAGE_PHASE1,
)

from tests.common import MockConfigEntry


async def test_charger_sensors(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test charger observation sensors."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(SENSOR_TOTAL_CHARGE_POWER)
    assert state
    assert state.state == "3.5"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfPower.KILO_WATT

    state = hass.states.get(SENSOR_CHARGER_MODE)
    assert state
    assert state.state == "connected_charging"

    state = hass.states.get(SENSOR_VOLTAGE_PHASE1)
    assert state
    assert state.state == "230.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfElectricPotential.VOLT

    state = hass.states.get(SENSOR_CURRENT_PHASE1)
    assert state
    assert state.state == "10.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfElectricCurrent.AMPERE

    state = hass.states.get(SENSOR_CHARGE_CURRENT_SET)
    assert state
    assert state.state == "16.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfElectricCurrent.AMPERE

    state = hass.states.get(SENSOR_SESSION_ENERGY)
    assert state
    assert state.state == "12.5"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.KILO_WATT_HOUR

    state = hass.states.get(SENSOR_LIFETIME_ENERGY)
    assert state
    assert state.state == "1234.5"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.KILO_WATT_HOUR

    state = hass.states.get(SENSOR_CHARGE_DURATION)
    assert state
    assert state.state == "3600.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTime.SECONDS

    state = hass.states.get(SENSOR_TEMPERATURE_INTERNAL)
    assert state
    assert state.state == "30.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS

    state = hass.states.get(SENSOR_HUMIDITY)
    assert state
    assert state.state == "40.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE

    state = hass.states.get(SENSOR_TAMPER)
    assert state
    assert state.state == "2.0"


async def test_installation_sensors(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test installation property sensors."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(SENSOR_INSTALLATION_AVAILABLE_CURRENT)
    assert state
    assert state.state == "32.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfElectricCurrent.AMPERE

    state = hass.states.get(SENSOR_INSTALLATION_ACTIVE_CHARGERS)
    assert state
    assert state.state == "1.0"


async def test_lifetime_energy_from_charger_detail(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, object],
) -> None:
    """Test lifetime energy can come from the charger detail endpoint."""
    charger_list_info = dict(CHARGER_INFO)
    charger_list_info.pop("signedMeterValueKwh")
    zaptec_get_responses["chargers?InstallationId=inst-1"] = {
        "data": [charger_list_info]
    }
    zaptec_get_responses[f"chargers/{CHARGER_ID}"] = {
        **CHARGER_INFO,
        "signedMeterValueKwh": 0.1,
    }

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(SENSOR_LIFETIME_ENERGY)
    assert state
    assert state.state == "0.1"


async def test_lifetime_energy_ignores_malformed_ocmf_payload(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, object],
) -> None:
    """Test malformed OCMF payloads do not raise from sensor state updates."""
    charger_info = dict(CHARGER_INFO)
    charger_info.pop("signedMeterValueKwh")
    zaptec_get_responses[f"chargers?InstallationId={INSTALLATION_ID}"] = {
        "data": [charger_info]
    }
    zaptec_get_responses[f"chargers/{CHARGER_ID}"] = charger_info
    zaptec_get_responses[f"chargers/{CHARGER_ID}/state"] = [
        *CHARGING_STATES,
        {
            "chargerId": CHARGER_ID,
            "stateId": 554,
            "stateName": "SignedMeterValue",
            "timestamp": "2026-08-16T10:00:00Z",
            "valueAsString": "OCMF|[]",
        },
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(SENSOR_LIFETIME_ENERGY)
    assert state
    assert state.state == STATE_UNKNOWN


async def test_sense_sensors_without_state(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Sense/P1 sensors are exposed when the state endpoint is unavailable."""
    entry = await setup_integration(hass, mock_config_entry)

    state = hass.states.get(SENSOR_SENSE_ACTIVE_POWER)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfPower.KILO_WATT

    dev_reg = dr.async_get(hass)
    device_entry = dev_reg.async_get_device_by_identifier(
        (DOMAIN, APM_ID), entry.entry_id
    )

    assert device_entry is not None
    assert device_entry.name == "Sense"
    assert device_entry.model == "Zaptec Sense"


async def test_sense_from_charger_list_is_treated_as_apm(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, object],
) -> None:
    """Test energy meter devices from the charger list do not get charger controls."""
    zaptec_get_responses[f"chargers?InstallationId={INSTALLATION_ID}"] = {
        "data": [
            {
                "id": APM_ID,
                "deviceId": "APH123",
                "name": "Sense",
                "deviceType": 3,
                "installationId": INSTALLATION_ID,
            }
        ]
    }

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(SENSOR_SENSE_ACTIVE_POWER)
    assert hass.states.get("button.sense_stop_charging") is None


async def test_sense_sensors_remain_after_fast_refresh(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test hierarchy-only devices remain available between hierarchy refreshes."""
    entry = await setup_integration(hass, mock_config_entry)

    await entry.runtime_data.coordinator.async_request_refresh()

    state = hass.states.get(SENSOR_SENSE_ACTIVE_POWER)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfPower.KILO_WATT


async def test_sense_sensors_with_state(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, object],
) -> None:
    """Test Sense/P1 observation sensors."""
    zaptec_get_responses[f"chargers/{APM_ID}/state"] = APM_STATES

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(SENSOR_SENSE_ACTIVE_POWER)
    assert state
    assert state.state == "4.2"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfPower.KILO_WATT

    state = hass.states.get(SENSOR_SENSE_ENERGY_IMPORTED)
    assert state
    assert state.state == "123.4"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.KILO_WATT_HOUR

    state = hass.states.get(SENSOR_SENSE_ENERGY_EXPORTED)
    assert state
    assert state.state == "12.3"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.KILO_WATT_HOUR


async def test_new_sense_sensors_are_added_after_hierarchy_refresh(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, object],
) -> None:
    """Test a new hierarchy-only Sense device is added without reload."""
    entry = await setup_integration(hass, mock_config_entry)

    zaptec_get_responses["installation/inst-1/hierarchy"] = HIERARCHY_WITH_NEW_APM
    entry.runtime_data.coordinator._cycle = HIERARCHY_REFRESH_CYCLES
    await entry.runtime_data.coordinator.async_request_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(SENSOR_SENSE_2_ACTIVE_POWER)
    assert state
    assert state.state == STATE_UNKNOWN
