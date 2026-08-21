"""Switch platform for the Zaptec integration."""

from datetime import UTC, datetime, timedelta
import logging
from typing import override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZaptecConfigEntry
from .api import ZaptecApiError, parse_bool, parse_float
from .const import (
    CMD_RESUME_CHARGING,
    CMD_STOP_CHARGING_FINAL,
    DOMAIN,
    OBS_FINAL_STOP_ACTIVE,
    OBS_NEXT_SCHEDULE_EVENT,
    OBS_PERMANENT_CABLE_LOCK,
    OPERATION_MODE_CHARGING,
    OPERATION_MODE_DISCONNECTED,
    OPERATION_MODE_FINISHED,
)
from .coordinator import ChargerData, ZaptecCoordinator
from .entity import ZaptecChargerEntity, has_write_role, require_write_role

_LOGGER = logging.getLogger(__name__)

LOCAL_SETTINGS_STALE_WINDOW = timedelta(minutes=30)


class ZaptecChargingSwitch(ZaptecChargerEntity, SwitchEntity):
    """Switch to stop and resume charging."""

    def __init__(
        self,
        coordinator: ZaptecCoordinator,
        entry: ZaptecConfigEntry,
        charger: ChargerData,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry, charger, description)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True while charging."""
        if (data := self.data) is None or data.operation_mode is None:
            return None
        return data.operation_mode == OPERATION_MODE_CHARGING

    @property
    @override
    def available(self) -> bool:
        """Switch is unavailable when no vehicle is connected."""
        data = self.data
        if data is None or data.operation_mode is None:
            return False
        return data.operation_mode != OPERATION_MODE_DISCONNECTED and has_write_role(
            data
        )

    @override
    async def async_turn_on(self, **kwargs: object) -> None:
        """Resume charging (command 507)."""
        data = self.data
        if data is None:
            raise HomeAssistantError(
                "Charger data unavailable",
                translation_domain=DOMAIN,
                translation_key="charger_data_unavailable",
            )
        require_write_role(data, str(self.charger.info.get("name") or "charger"))
        mode = data.operation_mode
        paused = (
            mode == OPERATION_MODE_FINISHED
            and parse_float(data.obs(OBS_FINAL_STOP_ACTIVE)) == 1
        )
        if not paused:
            if data.obs(OBS_NEXT_SCHEDULE_EVENT):
                raise HomeAssistantError(
                    "Cannot resume charging while a schedule event is pending",
                    translation_domain=DOMAIN,
                    translation_key="resume_schedule_pending",
                )
            raise HomeAssistantError(
                "Charging can only be resumed after being paused",
                translation_domain=DOMAIN,
                translation_key="resume_not_paused",
            )
        await self._async_send_command(CMD_RESUME_CHARGING, "resume charging")

    @override
    async def async_turn_off(self, **kwargs: object) -> None:
        """Pause charging with a final stop (command 506)."""
        data = self.data
        if data is None:
            raise HomeAssistantError(
                "Charger data unavailable",
                translation_domain=DOMAIN,
                translation_key="charger_data_unavailable",
            )
        require_write_role(data, str(self.charger.info.get("name") or "charger"))
        mode = data.operation_mode
        if mode == OPERATION_MODE_DISCONNECTED:
            raise HomeAssistantError(
                "Cannot stop charging: no vehicle connected",
                translation_domain=DOMAIN,
                translation_key="stop_no_vehicle",
            )
        if (
            mode == OPERATION_MODE_FINISHED
            and parse_float(data.obs(OBS_FINAL_STOP_ACTIVE)) == 1
        ):
            return  # already paused
        await self._async_send_command(CMD_STOP_CHARGING_FINAL, "stop charging")

    async def _async_send_command(self, command_id: int, action: str) -> None:
        """Send a charger command and refresh."""
        try:
            await self.coordinator.client.async_post(
                f"chargers/{self.charger.charger_id}/sendCommand/{command_id}"
            )
        except ZaptecApiError as err:
            raise HomeAssistantError(
                f"Failed to {action}",
                translation_domain=DOMAIN,
                translation_key="action_failed",
                translation_placeholders={"action": action, "error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()


class ZaptecPermanentCableLockSwitch(ZaptecChargerEntity, SwitchEntity):
    """Switch to control the permanent cable lock."""

    _assumed_lock: bool | None = None
    _assumed_lock_at: datetime | None = None

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True when the permanent cable lock is enabled."""
        if (data := self.data) is None:
            return None
        observed = parse_bool(data.obs(OBS_PERMANENT_CABLE_LOCK))
        if (
            self._assumed_lock is not None
            and self._assumed_lock_at is not None
            and datetime.now(UTC) - self._assumed_lock_at < LOCAL_SETTINGS_STALE_WINDOW
            and observed != self._assumed_lock
        ):
            return self._assumed_lock
        self._assumed_lock = None
        self._assumed_lock_at = None
        return observed

    @property
    @override
    def available(self) -> bool:
        """Return True if the cable lock state can be controlled."""
        data = self.data
        return (
            super().available
            and data is not None
            and data.obs(OBS_PERMANENT_CABLE_LOCK) is not None
            and has_write_role(data)
        )

    @override
    async def async_turn_on(self, **kwargs: object) -> None:
        """Enable the permanent cable lock."""
        await self._async_set_permanent_lock(True)

    @override
    async def async_turn_off(self, **kwargs: object) -> None:
        """Disable the permanent cable lock."""
        await self._async_set_permanent_lock(False)

    async def _async_set_permanent_lock(self, locked: bool) -> None:
        """Send the local settings update and refresh."""
        data = self.data
        if data is None:
            raise HomeAssistantError(
                "Charger data unavailable",
                translation_domain=DOMAIN,
                translation_key="charger_data_unavailable",
            )
        require_write_role(data, str(self.charger.info.get("name") or "charger"))
        try:
            await self.coordinator.client.async_post(
                f"chargers/{self.charger.charger_id}/localSettings",
                {"Cable": {"PermanentLock": locked}},
            )
        except ZaptecApiError as err:
            raise HomeAssistantError(
                "Failed to set cable lock",
                translation_domain=DOMAIN,
                translation_key="action_failed",
                translation_placeholders={
                    "action": "set cable lock",
                    "error": str(err),
                },
            ) from err
        self._assumed_lock = locked
        self._assumed_lock_at = datetime.now(UTC)
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZaptecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zaptec switches from a config entry."""
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
) -> list[SwitchEntity]:
    """Return newly discovered Zaptec switches."""
    data = coordinator.data
    if data is None:
        return []

    entities: list[SwitchEntity] = []
    charging_description = SwitchEntityDescription(
        key="charging", translation_key="charging"
    )
    cable_lock_description = SwitchEntityDescription(
        key="permanent_cable_lock",
        translation_key="permanent_cable_lock",
        entity_category=EntityCategory.CONFIG,
    )
    for charger in data["chargers"].values():
        if charger.is_apm or not has_write_role(charger):
            continue
        unique_id = f"{charger.charger_id}_charging"
        if unique_id not in known_entities:
            known_entities.add(unique_id)
            entities.append(
                ZaptecChargingSwitch(coordinator, entry, charger, charging_description)
            )
        unique_id = f"{charger.charger_id}_permanent_cable_lock"
        if (
            unique_id not in known_entities
            and charger.obs(OBS_PERMANENT_CABLE_LOCK) is not None
        ):
            known_entities.add(unique_id)
            entities.append(
                ZaptecPermanentCableLockSwitch(
                    coordinator, entry, charger, cable_lock_description
                )
            )

    return entities
