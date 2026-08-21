"""Test the Zaptec config flow."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant import config_entries
from homeassistant.components.zaptec.api import ZaptecAuthError, ZaptecConnectionError
from homeassistant.components.zaptec.const import CONF_INSTALLATIONS, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import setup_integration
from .const import (
    INSTALLATION,
    INSTALLATION_2,
    INSTALLATION_2_ID,
    INSTALLATION_ID,
    PASSWORD,
    USERNAME,
)

from tests.common import MockConfigEntry


async def test_form_shown(hass: HomeAssistant, mock_zaptec: MagicMock) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_form_single_installation(
    hass: HomeAssistant, mock_zaptec: MagicMock
) -> None:
    """Test we create an entry when the account has one installation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == USERNAME
    assert result2["data"] == {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    assert result2["options"] == {CONF_INSTALLATIONS: [INSTALLATION_ID]}


async def test_form_multiple_installations(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    zaptec_get_responses: dict[str, Any],
) -> None:
    """Test the installation selection step with multiple installations."""
    zaptec_get_responses["installation"] = {"data": [INSTALLATION, INSTALLATION_2]}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "installation"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_INSTALLATIONS: [INSTALLATION_2_ID]},
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["options"] == {CONF_INSTALLATIONS: [INSTALLATION_2_ID]}


async def test_form_invalid_auth(hass: HomeAssistant, mock_zaptec: MagicMock) -> None:
    """Test we handle invalid credentials."""
    mock_zaptec.async_get_access_token.side_effect = ZaptecAuthError(
        "Invalid credentials"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant, mock_zaptec: MagicMock) -> None:
    """Test we handle a connection error."""
    mock_zaptec.async_get_access_token.side_effect = ZaptecConnectionError(
        "Error connecting to Zaptec API"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_no_installations(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    zaptec_get_responses: dict[str, Any],
) -> None:
    """Test we abort when the account has no installations."""
    zaptec_get_responses["installation"] = {"data": []}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "no_installations"


async def test_form_duplicate_account(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort when the account is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the options flow updates the selected installations."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_INSTALLATIONS: [INSTALLATION_ID]},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_INSTALLATIONS: [INSTALLATION_ID]}


async def test_options_flow_cannot_connect(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow preserves connection errors."""
    await setup_integration(hass, mock_config_entry)
    mock_zaptec.async_get_access_token.side_effect = ZaptecConnectionError(
        "Error connecting to Zaptec API"
    )

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring an existing Zaptec entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: "new-password",
    }
    assert mock_config_entry.options == {CONF_INSTALLATIONS: [INSTALLATION_ID]}


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (ZaptecAuthError("Invalid credentials"), {"base": "invalid_auth"}),
        (
            ZaptecConnectionError("Error connecting to Zaptec API"),
            {"base": "cannot_connect"},
        ),
        (Exception("Unexpected error"), {"base": "unknown"}),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_zaptec: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_error: dict[str, str],
) -> None:
    """Test reconfigure flow handles validation errors."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_zaptec.async_get_access_token.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == expected_error
    assert mock_config_entry.data == {
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
    }

    mock_zaptec.async_get_access_token.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
