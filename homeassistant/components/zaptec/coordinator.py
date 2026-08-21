"""Data update coordinators for the Zaptec integration."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, TypedDict, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZaptecApiError, ZaptecAuthError, ZaptecClient, parse_float
from .const import (
    APM_DEVICE_TYPES,
    CHARGING_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    FIRMWARE_POLL_INTERVAL,
    LOGGER,
    OBS_CHARGER_OPERATION_MODE,
    OBS_WARNINGS,
)

HIERARCHY_REFRESH_CYCLES = 10


@dataclass(frozen=True)
class Observation:
    """A single charger state observation."""

    state_id: int
    value: str
    timestamp: datetime | None


@dataclass
class ChargerData:
    """Polled data for one charger (or APM device)."""

    info: dict[str, Any]
    observations: dict[int, Observation] = field(default_factory=dict)
    is_apm: bool = False

    @property
    def charger_id(self) -> str:
        """UUID of the charger."""
        return str(self.info["id"])

    @property
    def device_id(self) -> str:
        """Serial number of the charger."""
        return str(self.info.get("deviceId") or "")

    def obs(self, state_id: int) -> str | None:
        """Raw value of an observation, if present."""
        obs = self.observations.get(state_id)
        return obs.value if obs else None

    @property
    def operation_mode(self) -> int | None:
        """Current charger operation mode (observation 710 or info field)."""
        mode = parse_float(self.obs(OBS_CHARGER_OPERATION_MODE))
        if mode is None:
            mode = self.info.get("operatingMode")
        if mode is None:
            return None
        return int(mode)


@dataclass
class InstallationData:
    """Polled data for one installation."""

    info: dict[str, Any]
    hierarchy: dict[str, Any] = field(default_factory=dict)


class ZaptecData(TypedDict):
    """Data returned by the main Zaptec coordinator."""

    installations: dict[str, InstallationData]
    chargers: dict[str, ChargerData]


type ZaptecFirmwareData = dict[str, dict[str, Any]]


class ZaptecCoordinator(DataUpdateCoordinator[ZaptecData]):
    """Coordinator polling installations, chargers and charger state."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry[Any],
        client: ZaptecClient,
        installation_ids: list[str],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Zaptec",
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL),
        )
        self.client = client
        self.installation_ids = installation_ids
        self._entry_id = config_entry.entry_id
        self._cycle = 0
        self._warning_issue_ids: set[str] = set()

    @override
    async def _async_update_data(self) -> ZaptecData:
        """Fetch all data from the Zaptec API."""
        previous_data = self.data
        installations: dict[str, InstallationData] = {}
        chargers: dict[str, ChargerData] = {}

        refresh_hierarchy = self._cycle % HIERARCHY_REFRESH_CYCLES == 0
        self._cycle += 1

        try:
            for installation_id in self.installation_ids:
                info = await self.client.async_get(f"installation/{installation_id}")
                installations[installation_id] = InstallationData(info=info)
                if previous_data and installation_id in previous_data["installations"]:
                    installations[installation_id].hierarchy = previous_data[
                        "installations"
                    ][installation_id].hierarchy

                charger_list = await self.client.async_get(
                    f"chargers?InstallationId={installation_id}"
                )
                for charger_info in charger_list.get("data") or []:
                    charger_id = str(charger_info["id"])
                    try:
                        charger_detail = await self.client.async_get(
                            f"chargers/{charger_id}"
                        )
                        charger_info = {
                            **charger_info,
                            **{
                                key: value
                                for key, value in charger_detail.items()
                                if value is not None
                            },
                        }
                    except ZaptecAuthError:
                        raise
                    except ZaptecApiError as err:
                        LOGGER.debug("No charger detail for %s: %s", charger_id, err)
                    chargers[charger_id] = ChargerData(
                        info=charger_info,
                        is_apm=_is_apm_device(charger_info),
                    )

                if refresh_hierarchy:
                    hierarchy = await self.client.async_get(
                        f"installation/{installation_id}/hierarchy"
                    )
                    installations[installation_id].hierarchy = hierarchy
                    # Pick up devices present in the hierarchy but missing
                    # from the charger list (e.g. APM devices).
                    known = set(chargers)
                    for circuit in hierarchy.get("circuits") or []:
                        for device in circuit.get("chargers") or []:
                            device_id = str(device["id"])
                            if device_id not in known:
                                info = dict(device)
                                info["installationId"] = installation_id
                                info["circuitId"] = circuit.get("id")
                                info["circuitName"] = circuit.get("name")
                                info["circuitMaxCurrent"] = circuit.get("maxCurrent")
                                chargers[device_id] = ChargerData(
                                    info=info, is_apm=True
                                )
                    continue

                if previous_data:
                    for charger_id, charger in previous_data["chargers"].items():
                        if (
                            charger.is_apm
                            and charger.info.get("installationId") == installation_id
                        ):
                            chargers[charger_id] = ChargerData(
                                info=dict(charger.info), is_apm=True
                            )

            for charger_id, charger in chargers.items():
                try:
                    states = await self.client.async_get(f"chargers/{charger_id}/state")
                except ZaptecAuthError:
                    raise
                except ZaptecApiError as err:
                    if not charger.is_apm:
                        raise
                    LOGGER.debug("No state for %s: %s", charger_id, err)
                    continue
                for state in states or []:
                    try:
                        state_id = int(state["stateId"])
                    except KeyError, TypeError, ValueError:
                        continue
                    timestamp = None
                    if ts := state.get("timestamp"):
                        try:
                            timestamp = datetime.fromisoformat(str(ts))
                        except ValueError:
                            timestamp = None
                    charger.observations[state_id] = Observation(
                        state_id=state_id,
                        value=str(state.get("valueAsString") or ""),
                        timestamp=timestamp,
                    )

            self._update_warning_repair_issues(chargers)
        except ZaptecAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ZaptecApiError as err:
            raise UpdateFailed(str(err)) from err

        # Adapt the polling interval: faster while any vehicle is charging.
        charging = any(c.operation_mode == 3 for c in chargers.values())
        self.update_interval = timedelta(
            seconds=CHARGING_POLL_INTERVAL if charging else DEFAULT_POLL_INTERVAL
        )

        return {"installations": installations, "chargers": chargers}

    def _warning_issue_id(self, charger_id: str) -> str:
        """Return the repair issue ID for a charger warning."""
        return f"charger_warning_{self._entry_id}_{charger_id}"

    def async_clear_warning_repair_issues(self) -> None:
        """Clear active repair issues created by this coordinator."""
        for issue_id in self._warning_issue_ids:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        self._warning_issue_ids.clear()

    @staticmethod
    def _warning_details(charger: ChargerData) -> str | None:
        """Return active warning details for a charger."""
        if warnings := charger.info.get("warnings"):
            return str(warnings)
        warning_flags = parse_float(charger.obs(OBS_WARNINGS))
        if warning_flags is not None and warning_flags != 0:
            return f"warning flags {charger.obs(OBS_WARNINGS)}"
        return None

    def _update_warning_repair_issues(self, chargers: dict[str, ChargerData]) -> None:
        """Create or clear repair issues for active charger warnings."""
        active_issue_ids: set[str] = set()
        for charger_id, charger in chargers.items():
            if warning_details := self._warning_details(charger):
                issue_id = self._warning_issue_id(charger_id)
                active_issue_ids.add(issue_id)
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=False,
                    is_persistent=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="charger_warning",
                    translation_placeholders={
                        "charger_name": str(charger.info.get("name") or charger_id),
                        "warning_details": warning_details,
                    },
                )

        for issue_id in self._warning_issue_ids - active_issue_ids:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        self._warning_issue_ids = active_issue_ids


class ZaptecFirmwareCoordinator(DataUpdateCoordinator[ZaptecFirmwareData]):
    """Coordinator polling firmware info (slow-moving data)."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry[Any],
        client: ZaptecClient,
        installation_ids: list[str],
        main_coordinator: ZaptecCoordinator,
    ) -> None:
        """Initialize the firmware coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Zaptec firmware",
            update_interval=timedelta(seconds=FIRMWARE_POLL_INTERVAL),
        )
        self.client = client
        self.installation_ids = installation_ids
        self.main_coordinator = main_coordinator

    @override
    async def _async_update_data(self) -> ZaptecFirmwareData:
        """Fetch firmware status for all chargers of all installations."""
        firmware: dict[str, dict[str, Any]] = {}
        try:
            for installation_id in self.installation_ids:
                entries = await self.client.async_get(
                    f"chargerFirmware/installation/{installation_id}"
                )
                for entry in entries or []:
                    charger_id = entry.get("chargerId")
                    if charger_id:
                        firmware[str(charger_id)] = entry
        except ZaptecAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ZaptecApiError as err:
            raise UpdateFailed(str(err)) from err
        return firmware


def _is_apm_device(info: dict[str, Any]) -> bool:
    """Return True for Zaptec energy meter devices."""
    try:
        return int(info.get("deviceType") or 0) in APM_DEVICE_TYPES
    except TypeError, ValueError:
        return False
