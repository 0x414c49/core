"""Diagnostics support for the Zaptec integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import ZaptecConfigEntry

REDACT_KEYS = {"username", "password", "pin", "access_token", "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ZaptecConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    data = coordinator.data or {}

    return {
        "entry": async_redact_data(entry.as_dict(), REDACT_KEYS),
        "installations": {
            installation_id: {"info": inst.info, "hierarchy": inst.hierarchy}
            for installation_id, inst in data.get("installations", {}).items()
        },
        "chargers": {
            charger_id: {
                "info": charger.info,
                "observations": {
                    str(obs.state_id): obs.value
                    for obs in charger.observations.values()
                },
            }
            for charger_id, charger in data.get("chargers", {}).items()
        },
        "firmware": runtime.firmware.data or {},
    }
