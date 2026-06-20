"""Base entity for Fluidra Robot Cleaner."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FluidraCoordinator


class FluidraEntity(CoordinatorEntity[FluidraCoordinator]):
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: FluidraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = entry.data["device_id"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=entry.data.get("device_name", self._device_id),
            manufacturer="Fluidra / Zodiac",
            model="Freedom Lite CI3102",
            serial_number=self._device_id,
        )

    def _get_reported(self, cid: int):
        return self.coordinator.get_component_value(cid)
