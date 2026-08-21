"""The Zaptec integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ZaptecAuthError, ZaptecClient, ZaptecConnectionError
from .const import CONF_INSTALLATIONS, DOMAIN
from .coordinator import ZaptecCoordinator, ZaptecFirmwareCoordinator
from .entity import installation_device_info
from .models import ZaptecRuntimeData

type ZaptecConfigEntry = ConfigEntry[ZaptecRuntimeData]

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: ZaptecConfigEntry) -> bool:
    """Set up Zaptec from a config entry."""
    client = ZaptecClient(
        async_get_clientsession(hass),
        str(entry.data[CONF_USERNAME]),
        str(entry.data[CONF_PASSWORD]),
    )

    try:
        await client.async_get_access_token()
    except ZaptecAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except ZaptecConnectionError as err:
        raise ConfigEntryNotReady(str(err)) from err

    installation_ids = list(entry.options.get(CONF_INSTALLATIONS) or [])

    coordinator = ZaptecCoordinator(hass, entry, client, installation_ids)
    firmware_coordinator = ZaptecFirmwareCoordinator(
        hass, entry, client, installation_ids, coordinator
    )
    await coordinator.async_config_entry_first_refresh()
    await firmware_coordinator.async_refresh()

    dev_reg = dr.async_get(hass)
    for installation in coordinator.data["installations"].values():
        dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            **installation_device_info(installation),
        )

    entry.runtime_data = ZaptecRuntimeData(
        coordinator=coordinator, firmware=firmware_coordinator
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZaptecConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and entry.runtime_data is not None:
        entry.runtime_data.coordinator.async_clear_warning_repair_issues()
        entry.runtime_data.coordinator.client.invalidate_token()
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ZaptecConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device if it is no longer known by Zaptec."""
    if entry.runtime_data is None or entry.runtime_data.coordinator.data is None:
        return False

    data = entry.runtime_data.coordinator.data
    current_identifiers = {
        (DOMAIN, identifier) for identifier in data["installations"] | data["chargers"]
    }
    zaptec_identifiers = {
        identifier for identifier in device_entry.identifiers if identifier[0] == DOMAIN
    }
    return bool(zaptec_identifiers) and zaptec_identifiers.isdisjoint(
        current_identifiers
    )


async def _async_update_listener(hass: HomeAssistant, entry: ZaptecConfigEntry) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
