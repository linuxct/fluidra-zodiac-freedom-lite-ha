"""Binary sensor entities for Fluidra Robot Cleaner."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
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
            FluidraConnectedBinarySensor(coordinator, entry),
            FluidraCleaningBinarySensor(coordinator, entry),
            FluidraChargingBinarySensor(coordinator, entry),
            FluidraCycleEndedBinarySensor(coordinator, entry),
        ]
    )


class FluidraConnectedBinarySensor(FluidraEntity, BinarySensorEntity):
    _attr_name = "Connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_connected"

    @property
    def is_on(self) -> bool:
        device = self.coordinator.get_device_info()
        # Try connectivity field from device endpoint
        if device:
            connected = (device.get("connectivity") or {}).get("connected")
            if connected is not None:
                return bool(connected)
        # Fallback: state 11 = offline
        state = self._get_reported(15)
        if state is None:
            return False
        return int(state) != 11


class FluidraCleaningBinarySensor(FluidraEntity, BinarySensorEntity):
    _attr_name = "Cleaning"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:robot-vacuum-variant"

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_cleaning"

    @property
    def is_on(self) -> bool:
        state = self._get_reported(15)
        return state is not None and int(state) == 1


class FluidraChargingBinarySensor(FluidraEntity, BinarySensorEntity):
    _attr_name = "Charging"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_icon = "mdi:battery-charging"

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_charging"

    @property
    def is_on(self) -> bool:
        state = self._get_reported(15)
        return state is not None and int(state) in (2, 3)


class FluidraCycleEndedBinarySensor(FluidraEntity, BinarySensorEntity):
    _attr_name = "Cycle Ended"
    _attr_icon = "mdi:flag-checkered"

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_cycle_ended"

    @property
    def is_on(self) -> bool:
        return self._get_reported(31) == 1
