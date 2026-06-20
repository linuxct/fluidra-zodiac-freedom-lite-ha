"""Select entities for Fluidra Robot Cleaner (cleaning mode and pattern)."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CLEANING_MODE_INT_TO_LABEL,
    CLEANING_MODE_LABEL_TO_INT,
    CLEANING_MODE_OPTIONS,
    CLEANING_PATTERN_INT_TO_LABEL,
    CLEANING_PATTERN_LABEL_TO_INT,
    CLEANING_PATTERN_OPTIONS,
    DOMAIN,
)
from .coordinator import FluidraCoordinator
from .entity import FluidraEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FluidraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FluidraCleaningModeSelect(coordinator, entry),
            FluidraCleaningPatternSelect(coordinator, entry),
        ]
    )


class FluidraCleaningModeSelect(FluidraEntity, SelectEntity):
    _attr_name = "Cleaning Mode"
    _attr_icon = "mdi:broom"
    _attr_options = CLEANING_MODE_OPTIONS

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_cleaning_mode"

    @property
    def current_option(self) -> str | None:
        val = self._get_reported(16)
        if val is None:
            return None
        return CLEANING_MODE_INT_TO_LABEL.get(int(val))

    async def async_select_option(self, option: str) -> None:
        value = CLEANING_MODE_LABEL_TO_INT[option]
        await self.hass.async_add_executor_job(
            self.coordinator.api.update_component,
            self._device_id,
            16,
            value,
        )
        await self.coordinator.async_request_refresh()


class FluidraCleaningPatternSelect(FluidraEntity, SelectEntity):
    _attr_name = "Cleaning Pattern"
    _attr_icon = "mdi:swap-horizontal-bold"
    _attr_options = CLEANING_PATTERN_OPTIONS

    def __init__(self, coordinator: FluidraCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_id}_cleaning_pattern"

    @property
    def current_option(self) -> str | None:
        val = self._get_reported(17)
        if val is None:
            return None
        return CLEANING_PATTERN_INT_TO_LABEL.get(int(val))

    async def async_select_option(self, option: str) -> None:
        value = CLEANING_PATTERN_LABEL_TO_INT[option]
        await self.hass.async_add_executor_job(
            self.coordinator.api.update_component,
            self._device_id,
            17,
            value,
        )
        await self.coordinator.async_request_refresh()
