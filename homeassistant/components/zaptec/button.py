"""Button platform for the Zaptec integration."""

import logging
from typing import override

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZaptecConfigEntry
from .api import ZaptecApiError
from .const import (
    CMD_DEAUTHORIZE_AND_STOP,
    CMD_RESTART_CHARGER,
    CMD_RESUME_CHARGING,
    CMD_STOP_CHARGING_FINAL,
    DOMAIN,
)
from .coordinator import ZaptecCoordinator
from .entity import ZaptecChargerEntity, has_write_role, require_write_role

_LOGGER = logging.getLogger(__name__)

BUTTONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="resume_charging",
        translation_key="resume_charging",
    ),
    ButtonEntityDescription(
        key="stop_charging",
        translation_key="stop_charging",
    ),
    ButtonEntityDescription(
        key="deauthorize_and_stop",
        translation_key="deauthorize_and_stop",
    ),
    ButtonEntityDescription(
        key="restart_charger",
        translation_key="restart_charger",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

COMMAND_BY_KEY = {
    "resume_charging": CMD_RESUME_CHARGING,
    "stop_charging": CMD_STOP_CHARGING_FINAL,
    "deauthorize_and_stop": CMD_DEAUTHORIZE_AND_STOP,
    "restart_charger": CMD_RESTART_CHARGER,
}


class ZaptecChargerButton(ZaptecChargerEntity, ButtonEntity):
    """Button sending a charger command."""

    @override
    async def async_press(self) -> None:
        """Send the command."""
        require_write_role(self.data, str(self.charger.info.get("name") or "charger"))
        command_id = COMMAND_BY_KEY[self.entity_description.key]
        try:
            await self.coordinator.client.async_post(
                f"chargers/{self.charger.charger_id}/sendCommand/{command_id}"
            )
        except ZaptecApiError as err:
            raise HomeAssistantError(
                "Command failed",
                translation_domain=DOMAIN,
                translation_key="action_failed",
                translation_placeholders={"action": "send command", "error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZaptecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zaptec buttons from a config entry."""
    coordinator = entry.runtime_data.coordinator
    known_entities: set[str] = set()

    def add_new_entities() -> None:
        async_add_entities(_new_entities(coordinator, entry, known_entities))

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


def _new_entities(
    coordinator: ZaptecCoordinator,
    entry: ZaptecConfigEntry,
    known_entities: set[str],
) -> list[ButtonEntity]:
    """Return newly discovered Zaptec buttons."""
    data = coordinator.data
    if data is None:
        return []

    entities: list[ButtonEntity] = []
    for charger in data["chargers"].values():
        if charger.is_apm or not has_write_role(charger):
            continue
        for description in BUTTONS:
            unique_id = f"{charger.charger_id}_{description.key}"
            if unique_id in known_entities:
                continue
            known_entities.add(unique_id)
            entities.append(
                ZaptecChargerButton(coordinator, entry, charger, description)
            )

    return entities
