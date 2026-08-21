"""Models for the Zaptec integration."""

from dataclasses import dataclass

from .coordinator import ZaptecCoordinator, ZaptecFirmwareCoordinator


@dataclass
class ZaptecRuntimeData:
    """Runtime data attached to a Zaptec config entry."""

    coordinator: ZaptecCoordinator
    firmware: ZaptecFirmwareCoordinator
