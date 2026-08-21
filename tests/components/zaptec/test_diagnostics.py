"""Test the Zaptec diagnostics."""

from unittest.mock import MagicMock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.zaptec.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .conftest import setup_integration
from .const import APM_ID, CHARGER_ID, INSTALLATION_ID, PASSWORD, USERNAME

from tests.common import MockConfigEntry


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that credentials are redacted and charger data is present."""
    entry = await setup_integration(hass, mock_config_entry)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["data"][CONF_USERNAME] == REDACTED
    assert result["entry"]["data"][CONF_PASSWORD] == REDACTED

    assert USERNAME not in str(result)
    assert PASSWORD not in str(result)

    assert result["installations"][INSTALLATION_ID]["info"]["id"] == INSTALLATION_ID
    assert result["chargers"][CHARGER_ID]["info"]["id"] == CHARGER_ID
    assert result["chargers"][CHARGER_ID]["observations"]["513"] == "3.5"
    assert result["chargers"][APM_ID]["info"]["id"] == APM_ID
    assert result["firmware"][CHARGER_ID]["currentVersion"] == "2.1.1"
