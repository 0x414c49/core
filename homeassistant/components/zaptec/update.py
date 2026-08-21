"""Update platform for the Zaptec integration (firmware)."""

import logging
from typing import Any, override

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ZaptecConfigEntry
from .api import ZaptecApiError, ZaptecClient
from .const import CMD_UPGRADE_FIRMWARE, DOMAIN
from .coordinator import ChargerData, ZaptecCoordinator, ZaptecFirmwareCoordinator
from .entity import charger_device_info, has_write_role, require_write_role

_LOGGER = logging.getLogger(__name__)


def _version_parts(version: str | None) -> tuple[int, ...] | None:
    """Return numeric firmware version parts."""
    if not version:
        return None
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return None


def _has_newer_version(installed: str | None, available: str | None) -> bool:
    """Return True if available firmware is newer than installed firmware."""
    installed_parts = _version_parts(installed)
    available_parts = _version_parts(available)
    if installed_parts is None or available_parts is None:
        return bool(installed and available and installed != available)
    return available_parts > installed_parts


class ZaptecFirmwareUpdate(CoordinatorEntity[ZaptecFirmwareCoordinator], UpdateEntity):
    """Firmware update entity for a charger."""

    _attr_has_entity_name = True
    _attr_translation_key = "firmware"
    _attr_title = "Firmware"

    def __init__(
        self,
        firmware_coordinator: ZaptecFirmwareCoordinator,
        main_coordinator: ZaptecCoordinator,
        client: ZaptecClient,
        charger: ChargerData,
        entry: ZaptecConfigEntry,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(firmware_coordinator)
        self._main_coordinator = main_coordinator
        self._client = client
        self.charger = charger
        self._attr_unique_id = f"{charger.charger_id}_firmware"
        self._attr_device_info = charger_device_info(
            firmware_coordinator.hass,
            entry.entry_id,
            charger,
        )

    def _fw(self) -> dict[str, Any] | None:
        """Firmware info for this charger."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.charger.charger_id)

    @property
    def _charger_data(self) -> ChargerData | None:
        """Return fresh charger data from the main coordinator."""
        if self._main_coordinator.data is None:
            return None
        return self._main_coordinator.data["chargers"].get(self.charger.charger_id)

    @property
    @override
    def installed_version(self) -> str | None:
        """Currently installed firmware version."""
        fw = self._fw()
        if fw:
            return str(fw.get("currentVersion") or "") or None
        return None

    @property
    @override
    def latest_version(self) -> str | None:
        """Latest available firmware version."""
        fw = self._fw()
        if fw is None:
            return None
        current = str(fw.get("currentVersion") or "") or None
        available = str(fw.get("availableVersion") or "") or None
        if fw.get("isUpToDate", True) or not _has_newer_version(current, available):
            return current
        return available

    @property
    @override
    def supported_features(self) -> UpdateEntityFeature:
        """Install is supported when an update is available."""
        fw = self._fw()
        if (
            fw
            and not fw.get("isUpToDate", True)
            and _has_newer_version(self.installed_version, self.latest_version)
            and has_write_role(self._charger_data)
        ):
            return UpdateEntityFeature.INSTALL
        return UpdateEntityFeature(0)

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Start the firmware upgrade (command 200)."""
        charger = self._charger_data
        require_write_role(charger, str(self.charger.info.get("name") or "charger"))
        try:
            await self._client.async_post(
                f"chargers/{self.charger.charger_id}/sendCommand/{CMD_UPGRADE_FIRMWARE}"
            )
        except ZaptecApiError as err:
            raise HomeAssistantError(
                "Failed to start firmware update",
                translation_domain=DOMAIN,
                translation_key="action_failed",
                translation_placeholders={
                    "action": "start firmware update",
                    "error": str(err),
                },
            ) from err
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZaptecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zaptec update entities from a config entry."""
    runtime = entry.runtime_data
    known_entities: set[str] = set()

    def add_new_entities() -> None:
        async_add_entities(_new_entities(entry, known_entities))

    add_new_entities()
    entry.async_on_unload(runtime.coordinator.async_add_listener(add_new_entities))


def _new_entities(
    entry: ZaptecConfigEntry,
    known_entities: set[str],
) -> list[UpdateEntity]:
    """Return newly discovered Zaptec update entities."""
    runtime = entry.runtime_data
    data = runtime.coordinator.data
    if data is None:
        return []

    entities: list[UpdateEntity] = []
    for charger in data["chargers"].values():
        unique_id = f"{charger.charger_id}_firmware"
        if charger.is_apm or unique_id in known_entities or not has_write_role(charger):
            continue
        known_entities.add(unique_id)
        entities.append(
            ZaptecFirmwareUpdate(
                runtime.firmware,
                runtime.coordinator,
                runtime.coordinator.client,
                charger,
                entry,
            )
        )
    return entities
