"""Config flow for the Zaptec integration."""

import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow as ConfigFlowBase,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import ZaptecConfigEntry
from .api import ZaptecAuthError, ZaptecClient, ZaptecConnectionError
from .const import CONF_INSTALLATIONS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _async_list_installations(
    hass: HomeAssistant, username: str, password: str
) -> list[dict[str, Any]]:
    """Validate credentials and return accessible installations."""
    client = ZaptecClient(async_get_clientsession(hass), username, password)
    await client.async_get_access_token()
    result = await client.async_get("installation")
    return list(result.get("data") or [])


def _installation_options(
    installations: list[dict[str, Any]],
) -> list[selector.SelectOptionDict]:
    """Build labeled select options for the installation picker."""
    return [
        selector.SelectOptionDict(
            value=str(inst["id"]),
            label=str(inst.get("name") or "Installation"),
        )
        for inst in installations
    ]


class ZaptecConfigFlow(ConfigFlowBase, domain=DOMAIN):
    """Handle the Zaptec config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._username: str = ""
        self._password: str = ""
        self._installations: list[dict[str, Any]] = []

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the login step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            try:
                self._installations = await _async_list_installations(
                    self.hass, self._username, self._password
                )
            except ZaptecAuthError:
                errors["base"] = "invalid_auth"
            except ZaptecConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Zaptec login")
                errors["base"] = "unknown"
            else:
                if not self._installations:
                    return self.async_abort(reason="no_installations")
                await self.async_set_unique_id(self._username.lower())
                self._abort_if_unique_id_configured()
                if len(self._installations) == 1:
                    return self._async_create_entry_for(
                        [str(self._installations[0]["id"])]
                    )
                return await self.async_step_installation()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_installation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the installation selection step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = user_input.get(CONF_INSTALLATIONS) or []
            if not selected:
                errors["base"] = "no_installations_selected"
            else:
                return self._async_create_entry_for(selected)

        return self.async_show_form(
            step_id="installation",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INSTALLATIONS,
                        default=[str(inst["id"]) for inst in self._installations],
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=_installation_options(self._installations),
                            multiple=True,
                        )
                    )
                }
            ),
            errors=errors,
        )

    def _async_create_entry_for(self, installation_ids: list[str]) -> ConfigFlowResult:
        """Create the config entry."""
        return self.async_create_entry(
            title=self._username,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
            },
            options={CONF_INSTALLATIONS: installation_ids},
        )

    async def async_step_reauth(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauthentication."""
        self._username = str(user_input[CONF_USERNAME])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user for a new password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            try:
                await _async_list_installations(self.hass, self._username, password)
            except ZaptecAuthError:
                errors["base"] = "invalid_auth"
            except ZaptecConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        username = str(reconfigure_entry.data[CONF_USERNAME])

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            try:
                await _async_list_installations(self.hass, username, password)
            except ZaptecAuthError:
                errors["base"] = "invalid_auth"
            except ZaptecConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Zaptec reconfiguration")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ZaptecConfigEntry,
    ) -> ZaptecOptionsFlowHandler:
        """Return the options flow handler."""
        return ZaptecOptionsFlowHandler()


class ZaptecOptionsFlowHandler(OptionsFlow):
    """Handle options: change which installations are imported."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._installations: list[dict[str, Any]] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        entry = self.config_entry
        username = str(entry.data[CONF_USERNAME])
        password = str(entry.data[CONF_PASSWORD])

        if user_input is not None:
            selected = user_input.get(CONF_INSTALLATIONS) or []
            if not selected:
                errors["base"] = "no_installations_selected"
            else:
                return self.async_create_entry(
                    title="",
                    data={CONF_INSTALLATIONS: selected},
                )

        try:
            self._installations = await _async_list_installations(
                self.hass, username, password
            )
        except ZaptecAuthError, ZaptecConnectionError:
            errors["base"] = "cannot_connect"

        choices = _installation_options(self._installations)
        if not choices and "base" not in errors:
            errors["base"] = "no_installations"
        current = entry.options.get(CONF_INSTALLATIONS) or [
            opt["value"] for opt in choices
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INSTALLATIONS, default=current): (
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=choices,
                                multiple=True,
                            )
                        )
                    )
                }
            ),
            errors=errors,
        )
