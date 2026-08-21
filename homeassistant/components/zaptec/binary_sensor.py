"""Binary sensor platform for the Zaptec integration."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZaptecConfigEntry
from .api import parse_bool, parse_float
from .const import (
    MODE_CONNECTED,
    OBS_AUTHENTICATION_REQUIRED,
    OBS_IS_OCPP_CONNECTED,
    OBS_IS_ONLINE,
    OBS_WARNINGS,
    OPERATION_MODE_CHARGING,
)
from .coordinator import ChargerData, ZaptecCoordinator
from .entity import ZaptecChargerEntity, ZaptecInstallationEntity


class ZaptecChargingBinarySensor(ZaptecChargerEntity, BinarySensorEntity):
    """Represent whether the vehicle is charging."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True while charging."""
        if (data := self.data) is None or data.operation_mode is None:
            return None
        return data.operation_mode == OPERATION_MODE_CHARGING


class ZaptecCarConnectedBinarySensor(ZaptecChargerEntity, BinarySensorEntity):
    """Represent whether a vehicle is plugged in."""

    _attr_device_class = BinarySensorDeviceClass.PLUG

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True when a vehicle is connected."""
        if (data := self.data) is None or data.operation_mode is None:
            return None
        return data.operation_mode in MODE_CONNECTED


class ZaptecOnlineBinarySensor(ZaptecChargerEntity, BinarySensorEntity):
    """Represent whether the charger is connected to Zaptec Cloud."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True when online."""
        if (data := self.data) is None:
            return None
        online = data.info.get("isOnline")
        if online is not None:
            return bool(online)
        return parse_bool(data.obs(OBS_IS_ONLINE))


class ZaptecProblemBinarySensor(ZaptecChargerEntity, BinarySensorEntity):
    """Represent whether the charger has active warnings."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True when warnings are active."""
        if (data := self.data) is None:
            return None
        warnings = data.info.get("warnings")
        if warnings:
            return True
        flags = parse_float(data.obs(OBS_WARNINGS))
        if flags is not None:
            return flags != 0
        return False

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Expose the raw warning names."""
        if (data := self.data) is None:
            return None
        warnings = data.info.get("warnings")
        if warnings:
            return {"warnings": str(warnings)}
        return None


class ZaptecChargerBoolBinarySensor(ZaptecChargerEntity, BinarySensorEntity):
    """Represent a boolean charger observation."""

    def __init__(
        self,
        coordinator: ZaptecCoordinator,
        entry: ZaptecConfigEntry,
        charger: ChargerData,
        description: BinarySensorEntityDescription,
        obs_id: int,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry, charger, description)
        self._obs_id = obs_id

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the observation value."""
        if (data := self.data) is None:
            return None
        return parse_bool(data.obs(self._obs_id))


class ZaptecInstallationActiveBinarySensor(
    ZaptecInstallationEntity, BinarySensorEntity
):
    """Represent whether the installation is active."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True when the installation is active."""
        if (data := self.data) is None:
            return None
        active = data.info.get("active")
        return bool(active) if active is not None else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZaptecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zaptec binary sensors from a config entry."""
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
) -> list[BinarySensorEntity]:
    """Return newly discovered Zaptec binary sensors."""
    data = coordinator.data
    if data is None:
        return []

    entities: list[BinarySensorEntity] = []

    def add_charger_entity(
        entity: BinarySensorEntity, charger_id: str, key: str
    ) -> None:
        unique_id = f"{charger_id}_{key}"
        if unique_id in known_entities:
            return
        known_entities.add(unique_id)
        entities.append(entity)

    def add_installation_entity(
        entity: BinarySensorEntity, installation_id: str, key: str
    ) -> None:
        unique_id = f"{installation_id}_{key}"
        if unique_id in known_entities:
            return
        known_entities.add(unique_id)
        entities.append(entity)

    for charger in data["chargers"].values():
        if charger.is_apm:
            add_charger_entity(
                ZaptecChargerBoolBinarySensor(
                    coordinator,
                    entry,
                    charger,
                    _desc("online", BinarySensorDeviceClass.CONNECTIVITY),
                    OBS_IS_ONLINE,
                ),
                charger.charger_id,
                "online",
            )
            continue
        add_charger_entity(
            ZaptecChargingBinarySensor(coordinator, entry, charger, _desc("charging")),
            charger.charger_id,
            "charging",
        )
        add_charger_entity(
            ZaptecCarConnectedBinarySensor(
                coordinator, entry, charger, _desc("car_connected")
            ),
            charger.charger_id,
            "car_connected",
        )
        add_charger_entity(
            ZaptecOnlineBinarySensor(coordinator, entry, charger, _desc("online")),
            charger.charger_id,
            "online",
        )
        add_charger_entity(
            ZaptecProblemBinarySensor(coordinator, entry, charger, _desc("problem")),
            charger.charger_id,
            "problem",
        )
        if charger.obs(OBS_AUTHENTICATION_REQUIRED) is not None:
            add_charger_entity(
                ZaptecChargerBoolBinarySensor(
                    coordinator,
                    entry,
                    charger,
                    _desc("authorization_required"),
                    OBS_AUTHENTICATION_REQUIRED,
                ),
                charger.charger_id,
                "authorization_required",
            )
        if charger.obs(OBS_IS_OCPP_CONNECTED) is not None:
            add_charger_entity(
                ZaptecChargerBoolBinarySensor(
                    coordinator,
                    entry,
                    charger,
                    _desc("ocpp_connected", BinarySensorDeviceClass.CONNECTIVITY),
                    OBS_IS_OCPP_CONNECTED,
                ),
                charger.charger_id,
                "ocpp_connected",
            )

    for installation in data["installations"].values():
        if installation.info.get("active") is None:
            continue
        add_installation_entity(
            ZaptecInstallationActiveBinarySensor(
                coordinator,
                entry,
                installation,
                _desc("active", BinarySensorDeviceClass.CONNECTIVITY),
            ),
            str(installation.info["id"]),
            "active",
        )

    return entities


def _desc(key: str, device_class=None) -> BinarySensorEntityDescription:
    """Return a binary sensor description."""
    return BinarySensorEntityDescription(
        key=key,
        translation_key=key,
        **({"device_class": device_class} if device_class else {}),
    )
