"""Sensor entities for Fluidra Robot Cleaner."""

from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ROBOT_STATE_INT,
    CLEANING_MODE_INT_TO_LABEL,
    CLEANING_PATTERN_INT_TO_LABEL,
)
from .coordinator import FluidraCoordinator
from .entity import FluidraEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FluidraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FluidraStateSensor(coordinator, entry),
            FluidraBatterySensor(coordinator, entry),
            FluidraLastCleanSensor(coordinator, entry),
            FluidraLastSeenSensor(coordinator, entry),
            FluidraRSSISensor(coordinator, entry),
            FluidraIPSensor(coordinator, entry),
            FluidraFirmwareSensor(coordinator, entry),
            FluidraModeSensor(coordinator, entry),
            FluidraPatternSensor(coordinator, entry),
            FluidraScheduleDaysSensor(coordinator, entry),
            FluidraScheduleDurationSensor(coordinator, entry),
        ]
    )


class FluidraStateSensor(FluidraEntity, SensorEntity):
    _attr_name = "State"
    _attr_icon = "mdi:robot-vacuum"

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_state"

    @property
    def native_value(self) -> str | None:
        val = self._get_reported(15)
        if val is None:
            return None
        return ROBOT_STATE_INT.get(int(val), f"Unknown ({val})")

    @property
    def extra_state_attributes(self) -> dict:
        return {"state_code": self._get_reported(15)}


class FluidraBatterySensor(FluidraEntity, SensorEntity):
    _attr_name = "Battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_battery"

    @property
    def native_value(self) -> int | None:
        val = self._get_reported(26)
        return int(val) if val is not None else None


class FluidraLastCleanSensor(FluidraEntity, SensorEntity):
    _attr_name = "Last Clean"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:history"

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_last_clean"

    @property
    def native_value(self) -> datetime | None:
        raw = self._get_reported(28)
        if not raw:
            return None
        try:
            # Format: "YYYY-MM-DD HH:MM:SS"
            dt = datetime.strptime(str(raw)[:19], "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "raw": self._get_reported(28),
            "cycle_ended": self._get_reported(31) == 1,
        }


class FluidraRSSISensor(FluidraEntity, SensorEntity):
    _attr_name = "WiFi Signal"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_rssi"

    @property
    def native_value(self) -> int | None:
        val = self._get_reported(5)
        return int(val) if val is not None else None


class FluidraIPSensor(FluidraEntity, SensorEntity):
    _attr_name = "IP Address"
    _attr_icon = "mdi:ip-network"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_ip"

    @property
    def native_value(self) -> str | None:
        return self._get_reported(6)


class FluidraFirmwareSensor(FluidraEntity, SensorEntity):
    _attr_name = "Firmware Version"
    _attr_icon = "mdi:chip"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_firmware"

    @property
    def native_value(self) -> str | None:
        return self._get_reported(13)

    @property
    def device_info(self):
        from homeassistant.helpers.device_registry import DeviceInfo
        from .const import DOMAIN
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._entry.data.get("device_name", self._device_id),
            manufacturer="Fluidra / Zodiac",
            model="Freedom Lite CI3102",
            serial_number=self._device_id,
            sw_version=self.native_value,
        )


class FluidraModeSensor(FluidraEntity, SensorEntity):
    _attr_name = "Active Mode"
    _attr_icon = "mdi:broom"

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_mode_reported"

    @property
    def native_value(self) -> str | None:
        val = self._get_reported(16)
        if val is None:
            return None
        return CLEANING_MODE_INT_TO_LABEL.get(int(val), f"Unknown ({val})")


class FluidraPatternSensor(FluidraEntity, SensorEntity):
    _attr_name = "Active Pattern"
    _attr_icon = "mdi:swap-horizontal-bold"

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_pattern_reported"

    @property
    def native_value(self) -> str | None:
        val = self._get_reported(17)
        if val is None:
            return None
        return CLEANING_PATTERN_INT_TO_LABEL.get(int(val), f"Unknown ({val})")


class FluidraScheduleDaysSensor(FluidraEntity, SensorEntity):
    _attr_name = "Multi-day Schedule Days"
    _attr_icon = "mdi:calendar-clock"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_schedule_days"

    @property
    def native_value(self) -> int | None:
        sched = self._get_reported(36)
        if not isinstance(sched, dict):
            return None
        return sched.get("days")

    @property
    def extra_state_attributes(self) -> dict:
        sched = self._get_reported(36) or {}
        if not isinstance(sched, dict):
            return {}
        return {
            "hours": sched.get("hours"),
            "minutes": sched.get("minutes"),
            "duration_min": sched.get("duration"),
        }


class FluidraScheduleDurationSensor(FluidraEntity, SensorEntity):
    _attr_name = "Multi-day Schedule Duration"
    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_schedule_duration"

    @property
    def native_value(self) -> int | None:
        sched = self._get_reported(36)
        if not isinstance(sched, dict):
            return None
        return sched.get("duration")


class FluidraLastSeenSensor(FluidraEntity, RestoreSensor):
    """Timestamp of the last poll where the robot reported as connected.

    Uses RestoreSensor so the value survives HA restarts.
    """

    _attr_name = "Last Seen"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_last_seen"
        self._last_seen: datetime | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_sensor_data():
            try:
                self._last_seen = datetime.fromisoformat(
                    str(last_state.native_value)
                )
            except (ValueError, TypeError):
                pass

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._is_connected():
            self._last_seen = datetime.now(timezone.utc)
        self.async_write_ha_state()

    def _is_connected(self) -> bool:
        device = self.coordinator.get_device_info()
        if device:
            connected = (device.get("connectivity") or {}).get("connected")
            if connected is not None:
                return bool(connected)
        state = self.coordinator.get_component_value(15)
        return state is not None and int(state) != 11

    @property
    def native_value(self) -> datetime | None:
        return self._last_seen
