"""Test the Zaptec number platform."""

from typing import Any
from unittest.mock import MagicMock

from homeassistant.components.number import SERVICE_SET_VALUE
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfElectricCurrent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler

from .conftest import setup_integration
from .const import (
    CHARGER_INFO,
    INSTALLATION_ID,
    NUMBER_AVAILABLE_CURRENT,
    NUMBER_MAX_CHARGE_CURRENT_UNIQUE_ID,
    NUMBER_MIN_CHARGE_CURRENT_UNIQUE_ID,
    NUMBER_THREE_TO_ONE_PHASE_SWITCH_CURRENT,
)

from tests.common import MockConfigEntry


async def test_installation_available_current(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the available current number reflects the installation."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(NUMBER_AVAILABLE_CURRENT)
    assert state
    assert state.state == "32.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfElectricCurrent.AMPERE

    state = hass.states.get(NUMBER_THREE_TO_ONE_PHASE_SWITCH_CURRENT)
    assert state
    assert state.state == "16.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfElectricCurrent.AMPERE


async def test_set_installation_available_current(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the available current posts an installation update."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: NUMBER_AVAILABLE_CURRENT,
            "value": 25,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_zaptec.async_post.assert_called_once_with(
        f"installation/{INSTALLATION_ID}/update",
        {"availableCurrent": 25.0},
    )


async def test_set_three_to_one_phase_switch_current(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the 3 to 1-phase switch current posts an update."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: NUMBER_THREE_TO_ONE_PHASE_SWITCH_CURRENT,
            "value": 20,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_zaptec.async_post.assert_called_once_with(
        f"installation/{INSTALLATION_ID}/update",
        {"threeToOnePhaseSwitchCurrent": 20.0},
    )


async def test_charger_numbers_disabled_by_default(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test charger current limit numbers are disabled by default."""
    await setup_integration(hass, mock_config_entry)

    entity_registry = er.async_get(hass)
    max_current_entity_id = entity_registry.async_get_entity_id(
        "number", "zaptec", NUMBER_MAX_CHARGE_CURRENT_UNIQUE_ID
    )
    assert max_current_entity_id is not None
    max_current = entity_registry.async_get(max_current_entity_id)
    assert max_current is not None
    assert max_current.disabled_by is RegistryEntryDisabler.INTEGRATION

    min_current_entity_id = entity_registry.async_get_entity_id(
        "number", "zaptec", NUMBER_MIN_CHARGE_CURRENT_UNIQUE_ID
    )
    assert min_current_entity_id is not None
    min_current = entity_registry.async_get(min_current_entity_id)
    assert min_current is not None
    assert min_current.disabled_by is RegistryEntryDisabler.INTEGRATION


async def test_write_numbers_not_created_without_write_role(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    zaptec_get_responses: dict[str, Any],
) -> None:
    """Test write number entities are not created for accounts with User access only."""
    zaptec_get_responses[f"installation/{INSTALLATION_ID}"] = {
        **zaptec_get_responses[f"installation/{INSTALLATION_ID}"],
        "currentUserRoles": 1,
    }
    zaptec_get_responses[f"chargers?InstallationId={INSTALLATION_ID}"] = {
        "data": [{**CHARGER_INFO, "currentUserRoles": 1}]
    }

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(NUMBER_AVAILABLE_CURRENT) is None
    assert hass.states.get(NUMBER_THREE_TO_ONE_PHASE_SWITCH_CURRENT) is None
    entity_registry = er.async_get(hass)
    assert (
        entity_registry.async_get_entity_id(
            "number", "zaptec", NUMBER_MAX_CHARGE_CURRENT_UNIQUE_ID
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            "number", "zaptec", NUMBER_MIN_CHARGE_CURRENT_UNIQUE_ID
        )
        is None
    )
