"""Sensor platform for the Zaptec integration."""

import json
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZaptecConfigEntry
from .api import parse_float
from .const import (
    OBS_APM_ACTIVE_POWER,
    OBS_APM_ENERGY_EXPORT_TOTAL,
    OBS_APM_ENERGY_IMPORT_TOTAL,
    OBS_CHARGE_CURRENT_SET,
    OBS_CHARGE_DURATION,
    OBS_CHARGER_MAX_CURRENT,
    OBS_CHARGER_MIN_CURRENT,
    OBS_CHARGER_OPERATION_MODE,
    OBS_CURRENT_PHASE1,
    OBS_CURRENT_PHASE2,
    OBS_CURRENT_PHASE3,
    OBS_HUMIDITY,
    OBS_SIGNED_METER_VALUE,
    OBS_TAMPER_COVER,
    OBS_TEMPERATURE_INTERNAL5,
    OBS_TOTAL_CHARGE_POWER,
    OBS_TOTAL_CHARGE_POWER_SESSION,
    OBS_VOLTAGE_PHASE1,
    OBS_VOLTAGE_PHASE2,
    OBS_VOLTAGE_PHASE3,
)
from .coordinator import ChargerData, InstallationData, ZaptecCoordinator
from .entity import ZaptecChargerEntity, ZaptecInstallationEntity

CHARGER_MODE_OPTIONS = [
    "disconnected",
    "connected_requesting",
    "connected_charging",
    "connected_finished",
]

CHARGER_MODE_BY_ID = dict(zip((1, 2, 3, 5), CHARGER_MODE_OPTIONS, strict=True))

CHARGER_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="charger_mode",
        translation_key="charger_mode",
        device_class=SensorDeviceClass.ENUM,
        options=CHARGER_MODE_OPTIONS,
    ),
    SensorEntityDescription(
        key="total_charge_power",
        translation_key="total_charge_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage_phase1",
        translation_key="voltage_phase1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage_phase2",
        translation_key="voltage_phase2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage_phase3",
        translation_key="voltage_phase3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current_phase1",
        translation_key="current_phase1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current_phase2",
        translation_key="current_phase2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current_phase3",
        translation_key="current_phase3",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="charge_current_set",
        translation_key="charge_current_set",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="session_energy",
        translation_key="session_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="lifetime_energy",
        translation_key="lifetime_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="charge_duration",
        translation_key="charge_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="temperature_internal",
        translation_key="temperature_internal",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tamper_cover",
        translation_key="tamper_cover",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="max_charge_current",
        translation_key="max_charge_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="min_charge_current",
        translation_key="min_charge_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
)

INSTALLATION_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="available_current",
        translation_key="available_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="available_current_phase1",
        translation_key="available_current_phase1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="available_current_phase2",
        translation_key="available_current_phase2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="available_current_phase3",
        translation_key="available_current_phase3",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="max_current",
        translation_key="max_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="active_charger_count",
        translation_key="active_charger_count",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

APM_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="active_power",
        translation_key="active_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="energy_import_total",
        translation_key="energy_import_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energy_export_total",
        translation_key="energy_export_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

CHARGER_OBS_MAP = {
    OBS_TOTAL_CHARGE_POWER: "total_charge_power",
    OBS_VOLTAGE_PHASE1: "voltage_phase1",
    OBS_VOLTAGE_PHASE2: "voltage_phase2",
    OBS_VOLTAGE_PHASE3: "voltage_phase3",
    OBS_CURRENT_PHASE1: "current_phase1",
    OBS_CURRENT_PHASE2: "current_phase2",
    OBS_CURRENT_PHASE3: "current_phase3",
    OBS_CHARGE_CURRENT_SET: "charge_current_set",
    OBS_TOTAL_CHARGE_POWER_SESSION: "session_energy",
    OBS_SIGNED_METER_VALUE: "lifetime_energy",
    OBS_CHARGE_DURATION: "charge_duration",
    OBS_TEMPERATURE_INTERNAL5: "temperature_internal",
    OBS_HUMIDITY: "humidity",
    OBS_TAMPER_COVER: "tamper_cover",
    OBS_CHARGER_MAX_CURRENT: "max_charge_current",
    OBS_CHARGER_MIN_CURRENT: "min_charge_current",
}

APM_OBS_MAP = {
    OBS_APM_ACTIVE_POWER: "active_power",
    OBS_APM_ENERGY_IMPORT_TOTAL: "energy_import_total",
    OBS_APM_ENERGY_EXPORT_TOTAL: "energy_export_total",
}


def _observation_value(charger: ChargerData, state_id: int) -> float | None:
    return parse_float(charger.obs(state_id))


def _ocmf_meter_value(value: str | None) -> float | None:
    """Return the maximum reader value from an OCMF signed meter payload."""
    if not value:
        return None
    parts = value.split("|")
    if len(parts) not in (2, 3) or parts[0] != "OCMF":
        return parse_float(value)
    try:
        data = json.loads(parts[1])
        if not isinstance(data, dict):
            return None
        readings = data.get("RD") or []
        if not readings:
            return None
        return max(float(reading["RV"]) for reading in readings if "RV" in reading)
    except TypeError, ValueError, json.JSONDecodeError:
        return None


class ZaptecChargerSensor(ZaptecChargerEntity, SensorEntity):
    """Sensor for a charger observation."""

    _obs_id: int

    def __init__(
        self,
        coordinator: ZaptecCoordinator,
        entry: ZaptecConfigEntry,
        charger: ChargerData,
        description: SensorEntityDescription,
        obs_id: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, charger, description)
        self._obs_id = obs_id

    @property
    @override
    def native_value(self) -> float | None:
        """Return the observation as a number."""
        if (data := self.data) is None:
            return None
        return _observation_value(data, self._obs_id)


class ZaptecChargerModeSensor(ZaptecChargerEntity, SensorEntity):
    """Sensor for the charger operation mode."""

    @property
    @override
    def native_value(self) -> str | None:
        """Return the operation mode as an enum option."""
        if (data := self.data) is None or data.operation_mode is None:
            return None
        return CHARGER_MODE_BY_ID.get(data.operation_mode)


class ZaptecLifetimeEnergySensor(ZaptecChargerEntity, SensorEntity):
    """Lifetime energy from the charger info (signed meter value)."""

    @property
    @override
    def native_value(self) -> float | None:
        """Return the signed meter value in kWh."""
        if (data := self.data) is None:
            return None
        value = data.info.get("signedMeterValueKwh")
        if value is None:
            return _ocmf_meter_value(data.obs(OBS_SIGNED_METER_VALUE))
        try:
            return float(value)
        except TypeError, ValueError:
            return None


class ZaptecInstallationSensor(ZaptecInstallationEntity, SensorEntity):
    """Sensor for an installation property."""

    _key: str

    def __init__(
        self,
        coordinator: ZaptecCoordinator,
        entry: ZaptecConfigEntry,
        installation: InstallationData,
        description: SensorEntityDescription,
        key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, installation, description)
        self._key = key

    @property
    @override
    def native_value(self) -> float | None:
        """Return the installation property."""
        if (data := self.data) is None:
            return None
        value = data.info.get(self._key)
        if value is None:
            return None
        try:
            return float(value)
        except TypeError, ValueError:
            return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZaptecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zaptec sensors from a config entry."""
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
) -> list[SensorEntity]:
    """Return newly discovered Zaptec sensors."""
    data = coordinator.data
    if data is None:
        return []

    entities: list[SensorEntity] = []
    descriptions_by_key = {d.key: d for d in CHARGER_SENSORS}

    def add_charger_entity(entity: SensorEntity, charger_id: str, key: str) -> None:
        unique_id = f"{charger_id}_{key}"
        if unique_id in known_entities:
            return
        known_entities.add(unique_id)
        entities.append(entity)

    def add_installation_entity(
        entity: SensorEntity, installation_id: str, key: str
    ) -> None:
        unique_id = f"{installation_id}_{key}"
        if unique_id in known_entities:
            return
        known_entities.add(unique_id)
        entities.append(entity)

    for charger in data["chargers"].values():
        if charger.is_apm:
            apm_descriptions = {d.key: d for d in APM_SENSORS}
            for obs_id, key in APM_OBS_MAP.items():
                add_charger_entity(
                    ZaptecChargerSensor(
                        coordinator, entry, charger, apm_descriptions[key], obs_id
                    ),
                    charger.charger_id,
                    key,
                )
            continue

        if charger.operation_mode is not None:
            add_charger_entity(
                ZaptecChargerModeSensor(
                    coordinator, entry, charger, descriptions_by_key["charger_mode"]
                ),
                charger.charger_id,
                "charger_mode",
            )
        for obs_id, key in CHARGER_OBS_MAP.items():
            if obs_id == OBS_CHARGER_OPERATION_MODE:
                continue
            if key == "lifetime_energy":
                continue
            if charger.obs(obs_id) is not None:
                add_charger_entity(
                    ZaptecChargerSensor(
                        coordinator, entry, charger, descriptions_by_key[key], obs_id
                    ),
                    charger.charger_id,
                    key,
                )
        if (
            charger.info.get("signedMeterValueKwh") is not None
            or charger.obs(OBS_SIGNED_METER_VALUE) is not None
        ):
            add_charger_entity(
                ZaptecLifetimeEnergySensor(
                    coordinator,
                    entry,
                    charger,
                    descriptions_by_key["lifetime_energy"],
                ),
                charger.charger_id,
                "lifetime_energy",
            )

    inst_descriptions = {d.key: d for d in INSTALLATION_SENSORS}
    for installation in data["installations"].values():
        for key in (
            "availableCurrent",
            "availableCurrentPhase1",
            "availableCurrentPhase2",
            "availableCurrentPhase3",
            "maxCurrent",
            "activeChargerCount",
        ):
            if installation.info.get(key) is not None:
                sensor_key = _camel_to_snake(key)
                installation_id = str(installation.info["id"])
                add_installation_entity(
                    ZaptecInstallationSensor(
                        coordinator,
                        entry,
                        installation,
                        inst_descriptions[sensor_key],
                        key,
                    ),
                    installation_id,
                    sensor_key,
                )

    return entities


def _camel_to_snake(name: str) -> str:
    """Convert camelCase names to snake_case."""
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)
