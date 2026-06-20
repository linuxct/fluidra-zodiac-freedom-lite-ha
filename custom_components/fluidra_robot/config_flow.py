"""Config flow for Fluidra Robot Cleaner."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .api import AuthError, CognitoAuth, FluidraApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FluidraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._api: FluidraApi | None = None
        self._email: str = ""
        self._password: str = ""
        # Maps display label ("Pool / Robot Name") → config data dict
        self._robot_options: dict[str, dict[str, str]] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input["email"]
            password = user_input["password"]
            try:
                auth = CognitoAuth(email, password)
                api = FluidraApi(auth)
                robot_options = await self.hass.async_add_executor_job(
                    _fetch_robot_options, api
                )
                if not robot_options:
                    errors["base"] = "no_devices"
                else:
                    self._api = api
                    self._email = email
                    self._password = password
                    self._robot_options = robot_options
                    return await self.async_step_select_device()
            except AuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during Fluidra auth")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("email"): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if not self._robot_options:
            return self.async_abort(reason="no_devices")

        errors: dict[str, str] = {}

        if user_input is not None:
            selected_key = user_input["robot"]
            data = self._robot_options[selected_key]

            await self.async_set_unique_id(data["device_id"])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=data["device_name"],
                data={
                    "email": self._email,
                    "password": self._password,
                    "pool_id": data["pool_id"],
                    "pool_name": data["pool_name"],
                    "device_id": data["device_id"],
                    "device_name": data["device_name"],
                },
            )

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema(
                {
                    vol.Required("robot"): vol.In(list(self._robot_options.keys())),
                }
            ),
            errors=errors,
        )


def _fetch_robot_options(api: FluidraApi) -> dict[str, dict[str, str]]:
    """Build the pool/robot dropdown options. Runs in executor."""
    options: dict[str, dict[str, str]] = {}
    pools = api.get_pools()
    for pool in pools:
        pool_id = pool.get("id") or pool.get("poolId") or ""
        pool_name = pool.get("name") or pool_id
        try:
            devices = api.get_devices(pool_id)
        except Exception:
            continue
        for robot in api.find_robots(devices):
            device_id = robot.get("id") or ""
            device_name = (robot.get("info") or {}).get("name") or device_id
            label = f"{pool_name} → {device_name}"
            options[label] = {
                "pool_id": pool_id,
                "pool_name": pool_name,
                "device_id": device_id,
                "device_name": device_name,
            }
    return options
