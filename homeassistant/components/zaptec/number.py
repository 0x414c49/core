"""Number platform for the Zaptec integration."""

import logging
from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZaptecConfigEntry
from .api import ZaptecApiError, parse_float
from .const import DOMAIN, OBS_CHARGER_MAX_CURRENT, OBS_CHARGER_MIN_CURRENT
from .coordinator import ChargerData, InstallationData, ZaptecCoordinator
from .entity import (
    ZaptecChargerEntity,
    ZaptecInstallationEntity,
    has_write_role,
    require_write_role,
)

_LOGGER = logging.getLogger(__name__)

INSTALLATION_NUMBERS = (
    NumberEntityDescription(
        key="available_current",
        translation_key="available_current",
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="available_current_phase1",
        translation_key="available_current_phase1",
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="available_current_phase2",
        translation_key="available_current_phase2",
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="available_current_phase3",
        translation_key="available_current_phase3",
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="three_to_one_phase_switch_current",
        translation_key="three_to_one_phase_switch_current",
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        mode=NumberMode.BOX,
    ),
)

CHARGER_NUMBERS = (
    NumberEntityDescription(
        key="max_charge_current",
        translation_key="max_charge_current",
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        mode=NumberMode.BOX,
        entity_registry_enabled_default=False,
    ),
    NumberEntityDescription(
        key="min_charge_current",
        translation_key="min_charge_current",
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        mode=NumberMode.BOX,
        entity_registry_enabled_default=False,
    ),
)

INSTALLATION_FIELD_BY_KEY = {
    "available_current": "availableCurrent",
    "available_current_phase1": "availableCurrentPhase1",
    "available_current_phase2": "availableCurrentPhase2",
    "available_current_phase3": "availableCurrentPhase3",
    "three_to_one_phase_switch_current": "threeToOnePhaseSwitchCurrent",
}

CHARGER_OBS_BY_KEY = {
    "max_charge_current": OBS_CHARGER_MAX_CURRENT,
    "min_charge_current": OBS_CHARGER_MIN_CURRENT,
}


class ZaptecInstallationCurrentNumber(ZaptecInstallationEntity, NumberEntity):
    """Available current control for an installation (load balancing)."""

    def __init__(
        self,
        coordinator: ZaptecCoordinator,
        entry: ZaptecConfigEntry,
        installation: InstallationData,
        description: NumberEntityDescription,
        field: str,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, entry, installation, description)
        self._field = field
        max_current = installation.info.get("maxCurrent")
        self._attr_native_min_value = 0
        self._attr_native_max_value = (
            32
            if field == "threeToOnePhaseSwitchCurrent"
            else float(max_current)
            if max_current
            else 32
        )
        self._attr_native_step = 1

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current available current."""
        if (data := self.data) is None:
            return None
        value = data.info.get(self._field)
        try:
            return float(value) if value is not None else None
        except TypeError, ValueError:
            return None

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the available current."""
        require_write_role(
            self.data, str(self.installation.info.get("name") or "installation")
        )
        installation_id = str(self.installation.info["id"])
        try:
            await self.coordinator.client.async_post(
                f"installation/{installation_id}/update",
                {self._field: value},
            )
        except ZaptecApiError as err:
            raise HomeAssistantError(
                "Failed to set available current",
                translation_domain=DOMAIN,
                translation_key="action_failed",
                translation_placeholders={
                    "action": "set available current",
                    "error": str(err),
                },
            ) from err
        await self.coordinator.async_request_refresh()


class ZaptecChargerCurrentNumber(ZaptecChargerEntity, NumberEntity):
    """Charge current limit controls for a charger."""

    def __init__(
        self,
        coordinator: ZaptecCoordinator,
        entry: ZaptecConfigEntry,
        charger: ChargerData,
        description: NumberEntityDescription,
        obs_id: int,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, entry, charger, description)
        self._obs_id = obs_id
        self._attr_native_min_value = 0
        self._attr_native_max_value = 32
        self._attr_native_step = 1

    @property
    @override
    def native_value(self) -> float | None:
        """Return the configured limit."""
        if (data := self.data) is None:
            return None
        return parse_float(data.obs(self._obs_id))

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the charger current limit."""
        require_write_role(self.data, str(self.charger.info.get("name") or "charger"))
        field = (
            "maxChargeCurrent"
            if self.entity_description.key == "max_charge_current"
            else "minChargeCurrent"
        )
        try:
            await self.coordinator.client.async_post(
                f"chargers/{self.charger.charger_id}/update",
                {field: value},
            )
        except ZaptecApiError as err:
            raise HomeAssistantError(
                "Failed to set current limit",
                translation_domain=DOMAIN,
                translation_key="action_failed",
                translation_placeholders={
                    "action": "set current limit",
                    "error": str(err),
                },
            ) from err
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZaptecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zaptec number entities from a config entry."""
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
) -> list[NumberEntity]:
    """Return newly discovered Zaptec number entities."""
    data = coordinator.data
    if data is None:
        return []

    entities: list[NumberEntity] = []
    inst_desc = {d.key: d for d in INSTALLATION_NUMBERS}
    for installation in data["installations"].values():
        if not has_write_role(installation):
            continue
        for key, field in INSTALLATION_FIELD_BY_KEY.items():
            unique_id = f"{installation.info['id']}_{key}"
            if (
                unique_id not in known_entities
                and installation.info.get(field) is not None
            ):
                known_entities.add(unique_id)
                entities.append(
                    ZaptecInstallationCurrentNumber(
                        coordinator, entry, installation, inst_desc[key], field
                    )
                )

    charger_desc = {d.key: d for d in CHARGER_NUMBERS}
    for charger in data["chargers"].values():
        if charger.is_apm or not has_write_role(charger):
            continue
        for key, obs_id in CHARGER_OBS_BY_KEY.items():
            unique_id = f"{charger.charger_id}_{key}"
            if unique_id not in known_entities and charger.obs(obs_id) is not None:
                known_entities.add(unique_id)
                entities.append(
                    ZaptecChargerCurrentNumber(
                        coordinator, entry, charger, charger_desc[key], obs_id
                    )
                )

    return entities
