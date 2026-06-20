"""DataUpdateCoordinator for Fluidra Robot Cleaner."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FluidraApi
from .const import DOMAIN, SCAN_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class FluidraCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self, hass: HomeAssistant, api: FluidraApi, device_id: str
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}",
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.api = api
        self.device_id = device_id

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            components_list, device_info = await self.hass.async_add_executor_job(
                self._fetch_data
            )
        except Exception as err:
            raise UpdateFailed(f"Fluidra API error: {err}") from err

        components: dict[int, dict] = {
            c["id"]: c for c in components_list if "id" in c
        }
        return {"components": components, "device": device_info}

    def _fetch_data(self) -> tuple[list, dict]:
        components = self.api.get_components(self.device_id)
        try:
            device = self.api.get_device(self.device_id)
        except Exception:
            device = {}
        return components, device

    def get_component_value(self, cid: int) -> Any:
        if self.data is None:
            return None
        return self.data.get("components", {}).get(cid, {}).get("reportedValue")

    def get_device_info(self) -> dict:
        if self.data is None:
            return {}
        return self.data.get("device", {})
