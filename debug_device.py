#!/usr/bin/env python3
"""Dump raw API responses for the robot device."""
import json, os, sys
import requests
sys.path.insert(0, os.path.dirname(__file__))
from fluidra_robot import CognitoAuth, API_BASE

POOL_ID = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("FLUIDRA_POOL_ID", "")
DEVICE_ID = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("FLUIDRA_DEVICE_ID", "")
API_MOBILE = "https://api.fluidra-emea.com/mobile"

auth = CognitoAuth(os.environ["FLUIDRA_EMAIL"], os.environ["FLUIDRA_PASSWORD"])
token = auth.get_access_token()
headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def get(url, **params):
    r = requests.get(url, params=params or None, headers=headers, timeout=15)
    print(f"  HTTP {r.status_code}")
    try:
        return r.json()
    except Exception:
        return r.text


def section(title, url, **params):
    print(f"\n=== {title} ===")
    print(f"    {url}  params={params}")
    data = get(url, **params)
    print(json.dumps(data, indent=2))


# Generic API
section("generic /devices (tree)", f"{API_BASE}/devices", poolId=POOL_ID, format="tree")
section("generic /devices/{id}/components?deviceType=connected",
        f"{API_BASE}/devices/{DEVICE_ID}/components", deviceType="connected")

# Mobile API
section("mobile /v1/pools/{id}/devices", f"{API_MOBILE}/v1/pools/{POOL_ID}/devices")
section("mobile /v1/pools/current/devices", f"{API_MOBILE}/v1/pools/current/devices")
section("mobile /v1/pools/{poolId}/devices/{deviceId}/main",
        f"{API_MOBILE}/v1/pools/{POOL_ID}/devices/{DEVICE_ID}/main")
section("generic /devices/{id}/uiconfig", f"{API_BASE}/devices/{DEVICE_ID}/uiconfig")
