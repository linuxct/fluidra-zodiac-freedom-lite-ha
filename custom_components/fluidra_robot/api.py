"""Fluidra REST API + Cognito auth client (sync — run in executor)."""

from __future__ import annotations

import json
import time
from typing import Any

import requests

COGNITO_REGION = "eu-west-1"
COGNITO_CLIENT_ID = "g3njunelkcbtefosqm9bdhhq1"
COGNITO_ENDPOINT = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/"
API_BASE = "https://api.fluidra-emea.com/generic"


class AuthError(Exception):
    """Raised when Cognito authentication fails."""


class ApiError(Exception):
    """Raised when an API call returns a non-2xx response."""


class CognitoAuth:
    def __init__(self, email: str, password: str) -> None:
        self.email = email
        self.password = password
        self._tokens: dict | None = None
        self._token_expiry: float = 0.0

    def _do_auth(self) -> dict:
        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
        }
        body = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": COGNITO_CLIENT_ID,
            "AuthParameters": {
                "USERNAME": self.email,
                "PASSWORD": self.password,
            },
            "ClientMetadata": {
                "language": "en",
                "appId": "fluidraPool",
                "platform": "android",
            },
        }
        resp = requests.post(COGNITO_ENDPOINT, json=body, headers=headers, timeout=15)
        if resp.status_code != 200:
            try:
                err = resp.json()
                raise AuthError(
                    f"Cognito auth failed ({resp.status_code}): "
                    f"{err.get('__type', 'unknown')} – {err.get('message', resp.text)}"
                )
            except (json.JSONDecodeError, KeyError):
                raise AuthError(
                    f"Cognito auth failed ({resp.status_code}): {resp.text}"
                )
        return resp.json()["AuthenticationResult"]

    def _do_refresh(self) -> dict | None:
        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
        }
        body = {
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "ClientId": COGNITO_CLIENT_ID,
            "AuthParameters": {"REFRESH_TOKEN": self._tokens["RefreshToken"]},
        }
        resp = requests.post(COGNITO_ENDPOINT, json=body, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        result = resp.json()["AuthenticationResult"]
        result.setdefault("RefreshToken", self._tokens["RefreshToken"])
        return result

    def get_access_token(self) -> str:
        now = time.monotonic()
        if self._tokens and now < self._token_expiry - 60:
            return self._tokens["AccessToken"]

        if self._tokens and self._tokens.get("RefreshToken"):
            refreshed = self._do_refresh()
            if refreshed:
                self._tokens = refreshed
                self._token_expiry = now + refreshed.get("ExpiresIn", 3600)
                return self._tokens["AccessToken"]

        self._tokens = self._do_auth()
        self._token_expiry = now + self._tokens.get("ExpiresIn", 3600)
        return self._tokens["AccessToken"]


class FluidraApi:
    def __init__(self, auth: CognitoAuth) -> None:
        self.auth = auth
        self.session = requests.Session()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.auth.get_access_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get(self, path: str, params: dict | None = None) -> Any:
        url = f"{API_BASE}{path}"
        resp = self.session.get(url, headers=self._headers(), params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, body: dict, params: dict | None = None) -> Any:
        url = f"{API_BASE}{path}"
        resp = self.session.put(
            url, headers=self._headers(), json=body, params=params, timeout=15
        )
        if not resp.ok:
            raise ApiError(f"{resp.status_code} {resp.reason} — {resp.text}")
        return resp.json()

    def get_pools(self) -> list:
        return self._get("/users/me/pools")

    def get_devices(self, pool_id: str) -> list:
        return self._get("/devices", params={"poolId": pool_id, "format": "tree"})

    def get_device(self, device_id: str) -> dict:
        return self._get(f"/devices/{device_id}")

    def get_components(self, device_id: str) -> list:
        return self._get(
            f"/devices/{device_id}/components", params={"deviceType": "connected"}
        )

    def update_component(self, device_id: str, component_id: int, value: Any) -> Any:
        body = {"desiredValue": value}
        params = {"deviceType": "connected"}
        return self._put(
            f"/devices/{device_id}/components/{component_id}", body, params=params
        )

    def find_robots(self, devices: list) -> list:
        """Recursively find all robot cleaner devices in a device tree."""
        robots = []
        for device in devices:
            family = (device.get("info") or {}).get("family", "")
            legacy = device.get("deviceFamily", "")
            if "robot" in family.lower() or legacy == "robotCleaners":
                robots.append(device)
            robots.extend(self.find_robots(device.get("children", [])))
        return robots
