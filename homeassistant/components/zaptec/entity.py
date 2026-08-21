"""Base entities for the Zaptec integration."""

from typing import TYPE_CHECKING, override

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_TYPE_NAMES, DOMAIN, MANUFACTURER, SERIAL_MODEL_PREFIXES
from .coordinator import ChargerData, InstallationData, ZaptecCoordinator

if TYPE_CHECKING:
    from . import ZaptecConfigEntry

WRITE_ROLE_OWNER = 2
WRITE_ROLE_MAINTAINER = 4

ROLE_NAMES = {
    1: "User",
    WRITE_ROLE_OWNER: "Owner",
    WRITE_ROLE_MAINTAINER: "Maintainer",
    8: "Administrator",
    16: "Onboarding",
    32: "Device administrator",
    64: "Partner administrator",
    128: "Technical",
    256: "Internal data",
}


def charger_device_info(
    hass: HomeAssistant, config_entry_id: str, data: ChargerData
) -> DeviceInfo:
    """Build DeviceInfo for a charger or APM device."""
    serial = data.device_id
    model = SERIAL_MODEL_PREFIXES.get(serial[:3].upper())
    if not model:
        try:
            device_type = int(data.info.get("deviceType") or 0)
        except TypeError, ValueError:
            device_type = 0
        model = DEVICE_TYPE_NAMES.get(device_type, "Charger")
    info = DeviceInfo(
        identifiers={(DOMAIN, data.charger_id)},
        name=str(data.info.get("name") or "Charger"),
        manufacturer=MANUFACTURER,
        model=model,
        serial_number=serial or None,
    )
    if installation_id := data.info.get("installationId"):
        info["via_device_id"] = dr.async_get_device_id_by_identifier(
            hass,
            (DOMAIN, str(installation_id)),
            config_entry_id=config_entry_id,
        )
    return info


def installation_device_info(data: InstallationData) -> DeviceInfo:
    """Build DeviceInfo for an installation."""
    name = str(data.info.get("name") or "Installation")
    installation_type = "Pro" if data.info.get("installationType") == 0 else "Smart"
    return DeviceInfo(
        identifiers={(DOMAIN, str(data.info["id"]))},
        name=name,
        manufacturer=MANUFACTURER,
        model=f"Installation {installation_type}",
    )


def _current_user_roles(info: dict) -> int | None:
    """Return the current Zaptec user role bitmask, if reported."""
    roles = info.get("currentUserRoles")
    if roles is None:
        return None
    try:
        return int(roles)
    except TypeError, ValueError:
        return None


def _role_name(roles: int | None) -> str:
    """Return a readable role name for a Zaptec role bitmask."""
    if roles is None:
        return "Unknown"
    if roles == 0:
        return "None"
    names = [name for bit, name in ROLE_NAMES.items() if roles & bit]
    return ", ".join(names) or str(roles)


def has_write_role(data: ChargerData | InstallationData | None) -> bool:
    """Return True if the Zaptec object has Owner/Service-level write access."""
    if data is None:
        return False
    roles = _current_user_roles(data.info)
    return roles is None or bool(roles & (WRITE_ROLE_OWNER | WRITE_ROLE_MAINTAINER))


def require_write_role(
    data: ChargerData | InstallationData | None,
    object_name: str,
) -> None:
    """Raise if a Zaptec write endpoint would fail due to insufficient role."""
    if has_write_role(data):
        return
    roles = _current_user_roles(data.info) if data is not None else None
    raise HomeAssistantError(
        "This action requires Owner or Service access in Zaptec Portal",
        translation_domain=DOMAIN,
        translation_key="insufficient_role",
        translation_placeholders={
            "object_name": object_name,
            "role": _role_name(roles),
        },
    )


class ZaptecChargerEntity(CoordinatorEntity[ZaptecCoordinator]):
    """Base entity attached to a charger (or APM) device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ZaptecCoordinator,
        entry: ZaptecConfigEntry,
        charger: ChargerData,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.charger = charger
        self.entity_description = description
        self._attr_unique_id = f"{charger.charger_id}_{description.key}"
        self._attr_device_info = charger_device_info(
            coordinator.hass, entry.entry_id, charger
        )

    @property
    def data(self) -> ChargerData | None:
        """Return fresh charger data from the coordinator."""
        data = self.coordinator.data
        if data is None:
            return None
        return data["chargers"].get(self.charger.charger_id)

    @property
    @override
    def available(self) -> bool:
        """Return True if the device has been polled successfully."""
        return super().available and self.data is not None


class ZaptecInstallationEntity(CoordinatorEntity[ZaptecCoordinator]):
    """Base entity attached to an installation device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ZaptecCoordinator,
        entry: ZaptecConfigEntry,
        installation: InstallationData,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.installation = installation
        self.entity_description = description
        installation_id = str(installation.info["id"])
        self._attr_unique_id = f"{installation_id}_{description.key}"
        self._attr_device_info = installation_device_info(installation)

    @property
    def data(self) -> InstallationData | None:
        """Return fresh installation data from the coordinator."""
        data = self.coordinator.data
        if data is None:
            return None
        return data["installations"].get(str(self.installation.info["id"]))

    @property
    @override
    def available(self) -> bool:
        """Return True if the installation has been polled successfully."""
        return super().available and self.data is not None
