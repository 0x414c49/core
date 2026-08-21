"""Constants for Zaptec component tests."""

from typing import Any

USERNAME = "test-username"
PASSWORD = "test-password"

INSTALLATION_ID = "inst-1"
INSTALLATION_2_ID = "inst-2"
CHARGER_ID = "chg-1"
CHARGER_2_ID = "chg-2"
CHARGER_DEVICE_ID = "ZAP123456"
CHARGER_2_DEVICE_ID = "ZAP654321"
APM_ID = "apm-1"
APM_2_ID = "apm-2"
APM_DEVICE_ID = "APH123"
APM_2_DEVICE_ID = "APH456"

INSTALLATION = {
    "id": INSTALLATION_ID,
    "name": "Home",
    "installationType": 1,
    "active": True,
    "maxCurrent": 32,
    "availableCurrent": 32,
    "availableCurrentPhase1": 32,
    "availableCurrentPhase2": 32,
    "availableCurrentPhase3": 32,
    "threeToOnePhaseSwitchCurrent": 16,
    "activeChargerCount": 1,
}

INSTALLATION_2 = {
    "id": INSTALLATION_2_ID,
    "name": "Cabin",
    "installationType": 1,
    "active": True,
    "maxCurrent": 32,
    "availableCurrent": 32,
    "availableCurrentPhase1": 32,
    "availableCurrentPhase2": 32,
    "availableCurrentPhase3": 32,
    "activeChargerCount": 0,
}

HIERARCHY = {
    "id": INSTALLATION_ID,
    "name": "Home",
    "circuits": [
        {
            "id": "cir-1",
            "name": "Circuit 1",
            "maxCurrent": 32,
            "isActive": True,
            "chargers": [
                {
                    "id": CHARGER_ID,
                    "deviceId": CHARGER_DEVICE_ID,
                    "name": "Garage",
                    "active": True,
                    "deviceType": 1,
                },
                {
                    "id": APM_ID,
                    "deviceId": APM_DEVICE_ID,
                    "name": "Sense",
                    "active": True,
                    "deviceType": 3,
                },
            ],
        }
    ],
}

HIERARCHY_WITH_NEW_APM = {
    **HIERARCHY,
    "circuits": [
        {
            **HIERARCHY["circuits"][0],
            "chargers": [
                *HIERARCHY["circuits"][0]["chargers"],
                {
                    "id": APM_2_ID,
                    "deviceId": APM_2_DEVICE_ID,
                    "name": "Sense 2",
                    "active": True,
                    "deviceType": 3,
                },
            ],
        }
    ],
}


def _charger_info(operating_mode: int) -> dict[str, Any]:
    return {
        "id": CHARGER_ID,
        "deviceId": CHARGER_DEVICE_ID,
        "name": "Garage",
        "deviceType": 1,
        "operatingMode": operating_mode,
        "isOnline": True,
        "installationId": INSTALLATION_ID,
        "installationName": "Home",
        "signedMeterValueKwh": 1234.5,
        "warnings": None,
    }


CHARGER_INFO = _charger_info(3)
CHARGER_2_INFO = {
    **_charger_info(3),
    "id": CHARGER_2_ID,
    "deviceId": CHARGER_2_DEVICE_ID,
    "name": "Driveway",
}
CHARGER_INFO_PAUSED = _charger_info(5)
CHARGER_INFO_DISCONNECTED = _charger_info(1)


def _state(state_id: int, state_name: str, value: str) -> dict[str, Any]:
    return {
        "chargerId": CHARGER_ID,
        "stateId": state_id,
        "stateName": state_name,
        "timestamp": "2026-08-16T10:00:00Z",
        "valueAsString": value,
    }


CHARGING_STATE_VALUES: dict[int, tuple[str, str]] = {
    120: ("AuthenticationRequired", "true"),
    151: ("PermanentCableLock", "false"),
    513: ("TotalChargePower", "3.5"),
    501: ("VoltagePhase1", "230"),
    502: ("VoltagePhase2", "230"),
    503: ("VoltagePhase3", "230"),
    507: ("CurrentPhase1", "10"),
    508: ("CurrentPhase2", "0"),
    509: ("CurrentPhase3", "0"),
    708: ("ChargeCurrentSet", "16"),
    553: ("TotalChargePowerSession", "12.5"),
    701: ("ChargeDuration", "3600"),
    201: ("TemperatureInternal5", "30"),
    270: ("Humidity", "40"),
    280: ("TamperCover", "2"),
    510: ("ChargerMaxCurrent", "32"),
    511: ("ChargerMinCurrent", "6"),
    710: ("ChargerOperationMode", "3"),
    804: ("Warnings", "0"),
}


def _states(
    overrides: dict[int, tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    values = dict(CHARGING_STATE_VALUES)
    values.update(overrides or {})
    return [_state(state_id, name, value) for state_id, (name, value) in values.items()]


CHARGING_STATES = _states()
CHARGING_STATES_WITH_OCPP = _states({125: ("OCPPConnected", "true")})
PAUSED_STATES = _states(
    {710: ("ChargerOperationMode", "5"), 718: ("FinalStopActive", "1")}
)
DISCONNECTED_STATES = _states({710: ("ChargerOperationMode", "1")})

FIRMWARE = [
    {
        "chargerId": CHARGER_ID,
        "deviceId": CHARGER_DEVICE_ID,
        "isOnline": True,
        "currentVersion": "2.1.1",
        "availableVersion": "2.1.1",
        "isUpToDate": True,
        "deviceType": 1,
    }
]

FIRMWARE_UPDATE_AVAILABLE = [
    {
        "chargerId": CHARGER_ID,
        "deviceId": CHARGER_DEVICE_ID,
        "isOnline": True,
        "currentVersion": "2.1.1",
        "availableVersion": "2.2.0",
        "isUpToDate": False,
        "deviceType": 1,
    }
]

SENSOR_TOTAL_CHARGE_POWER = "sensor.garage_total_charge_power"
SENSOR_CHARGER_MODE = "sensor.garage_charger_mode"
SENSOR_VOLTAGE_PHASE1 = "sensor.garage_voltage_phase_1"
SENSOR_CURRENT_PHASE1 = "sensor.garage_current_phase_1"
SENSOR_CHARGE_CURRENT_SET = "sensor.garage_charge_current"
SENSOR_SESSION_ENERGY = "sensor.garage_session_energy"
SENSOR_LIFETIME_ENERGY = "sensor.garage_lifetime_energy"
SENSOR_CHARGE_DURATION = "sensor.garage_charge_duration"
SENSOR_TEMPERATURE_INTERNAL = "sensor.garage_internal_temperature"
SENSOR_HUMIDITY = "sensor.garage_humidity"
SENSOR_TAMPER = "sensor.garage_tamper"
SENSOR_INSTALLATION_AVAILABLE_CURRENT = "sensor.home_available_current"
SENSOR_INSTALLATION_MAX_CURRENT = "sensor.home_max_current"
SENSOR_INSTALLATION_ACTIVE_CHARGERS = "sensor.home_active_chargers"
SENSOR_SENSE_ACTIVE_POWER = "sensor.sense_active_power"
SENSOR_SENSE_ENERGY_IMPORTED = "sensor.sense_energy_imported"
SENSOR_SENSE_ENERGY_EXPORTED = "sensor.sense_energy_exported"
SENSOR_DRIVEWAY_TOTAL_CHARGE_POWER = "sensor.driveway_total_charge_power"
SENSOR_SENSE_2_ACTIVE_POWER = "sensor.sense_2_active_power"

APM_STATES = [
    {
        "chargerId": APM_ID,
        "stateId": 1161,
        "stateName": "ActivePower",
        "timestamp": "2026-08-16T10:00:00Z",
        "valueAsString": "4.2",
    },
    {
        "chargerId": APM_ID,
        "stateId": 1020,
        "stateName": "EnergyImportTotal",
        "timestamp": "2026-08-16T10:00:00Z",
        "valueAsString": "123.4",
    },
    {
        "chargerId": APM_ID,
        "stateId": 1021,
        "stateName": "EnergyExportTotal",
        "timestamp": "2026-08-16T10:00:00Z",
        "valueAsString": "12.3",
    },
]

BINARY_SENSOR_CHARGING = "binary_sensor.garage_charging"
BINARY_SENSOR_CAR_CONNECTED = "binary_sensor.garage_car_connected"
BINARY_SENSOR_ONLINE = "binary_sensor.garage_online"
BINARY_SENSOR_PROBLEM = "binary_sensor.garage_problem"
BINARY_SENSOR_AUTHORIZATION_REQUIRED = "binary_sensor.garage_authorization_required"
BINARY_SENSOR_DRIVEWAY_CHARGING = "binary_sensor.driveway_charging"
BINARY_SENSOR_DRIVEWAY_OCPP_CONNECTED = "binary_sensor.driveway_ocpp_connected"

SWITCH_CHARGING = "switch.garage_charging"
SWITCH_PERMANENT_CABLE_LOCK = "switch.garage_permanent_cable_lock"
SWITCH_DRIVEWAY_CHARGING = "switch.driveway_charging"

NUMBER_AVAILABLE_CURRENT = "number.home_available_current"
NUMBER_THREE_TO_ONE_PHASE_SWITCH_CURRENT = "number.home_3_to_1_phase_switch_current"
NUMBER_MAX_CHARGE_CURRENT_UNIQUE_ID = f"{CHARGER_ID}_max_charge_current"
NUMBER_MIN_CHARGE_CURRENT_UNIQUE_ID = f"{CHARGER_ID}_min_charge_current"
NUMBER_DRIVEWAY_MAX_CHARGE_CURRENT = "number.driveway_max_charge_current"

BUTTON_RESUME_CHARGING = "button.garage_resume_charging"
BUTTON_STOP_CHARGING = "button.garage_stop_charging"
BUTTON_DEAUTHORIZE_AND_STOP = "button.garage_deauthorize_and_stop"
BUTTON_RESTART_CHARGER = "button.garage_restart_charger"
BUTTON_DRIVEWAY_STOP_CHARGING = "button.driveway_stop_charging"

UPDATE_FIRMWARE_UNIQUE_ID = f"{CHARGER_ID}_firmware"
UPDATE_DRIVEWAY_FIRMWARE = "update.driveway_firmware"
