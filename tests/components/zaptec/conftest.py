"""Common fixtures for the Zaptec tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.zaptec.api import ZaptecApiError
from homeassistant.components.zaptec.const import CONF_INSTALLATIONS, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import (
    CHARGER_ID,
    CHARGER_INFO,
    CHARGING_STATES,
    FIRMWARE,
    HIERARCHY,
    INSTALLATION,
    INSTALLATION_ID,
    PASSWORD,
    USERNAME,
)

from tests.common import MockConfigEntry


@pytest.fixture
def zaptec_get_responses() -> dict[str, Any]:
    """Default GET responses indexed by API path."""
    return {
        "installation": {"data": [INSTALLATION]},
        f"installation/{INSTALLATION_ID}": INSTALLATION,
        f"installation/{INSTALLATION_ID}/hierarchy": HIERARCHY,
        f"chargers?InstallationId={INSTALLATION_ID}": {"data": [CHARGER_INFO]},
        f"chargers/{CHARGER_ID}": CHARGER_INFO,
        f"chargers/{CHARGER_ID}/state": CHARGING_STATES,
        f"chargerFirmware/installation/{INSTALLATION_ID}": FIRMWARE,
    }


@pytest.fixture
def mock_zaptec(
    zaptec_get_responses: dict[str, Any],
) -> Generator[MagicMock]:
    """Mock the Zaptec API client."""
    client = MagicMock()
    client.async_get_access_token = AsyncMock(return_value="test-access-token")

    async def async_get(path: str) -> Any:
        """Serve canned responses; missing paths mimic an API failure."""
        if path in zaptec_get_responses:
            if isinstance(zaptec_get_responses[path], Exception):
                raise zaptec_get_responses[path]
            return zaptec_get_responses[path]
        raise ZaptecApiError(f"Zaptec API GET {path} failed: 404")

    client.async_get = AsyncMock(side_effect=async_get)
    client.async_post = AsyncMock(return_value={})
    client.invalidate_token = MagicMock()

    with (
        patch(
            "homeassistant.components.zaptec.ZaptecClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.zaptec.config_flow.ZaptecClient",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
        options={CONF_INSTALLATIONS: [INSTALLATION_ID]},
        unique_id=USERNAME,
    )


async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the Zaptec integration."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
