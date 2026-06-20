#!/usr/bin/env python3
"""
Fluidra Pool Robot Controller
Controls Zodiac Freedom Lite CI3102 (and other Fluidra Robot Cleaners) via the cloud API.

Component map (confirmed from uiconfig + live API):
  1  = serial number (ro)         2  = thingType (ro)
  3  = hw version (ro)            4  = SKU (ro)
  5  = WiFi RSSI (ro)             6  = IP address (ro)
  7  = OTA job ID (write to OTA)  8  = BLE access code (ro)
  9  = {request,response} cmd ch  10 = unknown
  11 = timezone                   12 = cloud region flag
  13 = firmware version (ro)      14 = unknown
  15 = STATE (ro) — see ROBOT_STATES
  16 = CLEANING MODE (rw) — see CLEANING_MODES
  17 = CLEANING PATTERN (rw) — see CLEANING_PATTERNS
  18 = schedule array             26 = battery % (ro)
  28 = last clean datetime (ro)   31 = cycle-end flag (ro)
  36 = {days,hours,mins,duration} 37 = multiday schedule encoded

State values (component 15, read-only — robot manages transitions):
  0=submerge/ready  1=cleaning  2=charging  3=charged/docked
  10=pickup/lift    11=offline

Cleaning mode values (component 16):
  1=floor_walls  2=floor  3=walls  4=waterline  5=multiday

Pattern values (component 17):
  0=s_pattern  1=standard

Usage:
  python fluidra_robot.py --status
  python fluidra_robot.py --mode floor_walls
  python fluidra_robot.py --pattern standard
  python fluidra_robot.py --set-component 16 2

Credentials:
  FLUIDRA_EMAIL / --email
  FLUIDRA_PASSWORD / --password
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests", file=sys.stderr)
    sys.exit(1)

# ──────────────────────────────────────────────────────────────
# Constants (extracted from libapp.so via blutter decompilation)
# ──────────────────────────────────────────────────────────────

COGNITO_REGION = "eu-west-1"
COGNITO_CLIENT_ID = "g3njunelkcbtefosqm9bdhhq1"
COGNITO_ENDPOINT = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/"

API_BASE = "https://api.fluidra-emea.com/generic"

# Component 15 state integer values (from uiconfig live analysis)
ROBOT_STATE_INT = {
    0:  "Submerge/Ready",
    1:  "Cleaning",
    2:  "Charging",
    3:  "Charged (docked)",
    10: "Pick-up / Lift",
    11: "Offline",
}

# Component 16 cleaning mode integer values
CLEANING_MODES = {
    "floor_walls": (1, "Floor & Walls"),
    "floor":       (2, "Floor only"),
    "walls":       (3, "Walls only"),
    "waterline":   (4, "Waterline only"),
    "multiday":    (5, "Multi-day"),
}

# Component 17 pattern integer values
CLEANING_PATTERNS = {
    "s_pattern": (0, "S-Pattern"),
    "standard":  (1, "Standard"),
}


# ──────────────────────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────────────────────

class CognitoAuth:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self._tokens: Optional[dict] = None
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
            "ClientMetadata": {"language": "en", "appId": "fluidraPool", "platform": "android"},
        }
        resp = requests.post(COGNITO_ENDPOINT, json=body, headers=headers, timeout=15)
        if resp.status_code != 200:
            try:
                err = resp.json()
                raise RuntimeError(
                    f"Cognito auth failed ({resp.status_code}): "
                    f"{err.get('__type', 'unknown')} – {err.get('message', resp.text)}"
                )
            except json.JSONDecodeError:
                raise RuntimeError(f"Cognito auth failed ({resp.status_code}): {resp.text}")
        return resp.json()["AuthenticationResult"]

    def _do_refresh(self) -> dict:
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


# ──────────────────────────────────────────────────────────────
# API Client
# ──────────────────────────────────────────────────────────────

class FluidraApi:
    def __init__(self, auth: CognitoAuth):
        self.auth = auth
        self.session = requests.Session()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.auth.get_access_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get(self, path: str, params: dict = None) -> dict | list:
        url = f"{API_BASE}{path}"
        resp = self.session.get(url, headers=self._headers(), params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, body: dict, params: dict = None) -> dict:
        url = f"{API_BASE}{path}"
        resp = self.session.put(url, headers=self._headers(), json=body,
                                params=params, timeout=15)
        if not resp.ok:
            raise requests.exceptions.HTTPError(
                f"{resp.status_code} {resp.reason} for url: {url}\nBody: {resp.text}",
                response=resp,
            )
        return resp.json()

    def get_pools(self) -> list:
        return self._get("/users/me/pools")

    def get_devices(self, pool_id: str) -> list:
        # NOTE: format=tree does NOT include components — fetch them separately
        return self._get("/devices", params={"poolId": pool_id, "format": "tree"})

    def get_components(self, device_id: str) -> list:
        return self._get(f"/devices/{device_id}/components",
                         params={"deviceType": "connected"})

    def update_component(self, device_id: str, component_id: int, value) -> dict:
        # deviceType as query param (mirrors GET pattern); desiredValue in body
        body = {"desiredValue": value}
        params = {"deviceType": "connected"}
        return self._put(f"/devices/{device_id}/components/{component_id}",
                         body, params=params)


# ──────────────────────────────────────────────────────────────
# Robot helpers
# ──────────────────────────────────────────────────────────────

def is_robot_cleaner(device: dict) -> bool:
    """Detect robot cleaners by info.family (actual field from live API)."""
    family = device.get("info", {}).get("family", "")
    # Also accept legacy deviceFamily field if present
    legacy = device.get("deviceFamily", "")
    return "robot" in family.lower() or legacy == "robotCleaners"


def find_robots(devices: list) -> list:
    """Recursively collect all robot cleaner devices from a device tree."""
    robots = []
    for device in devices:
        if is_robot_cleaner(device):
            robots.append(device)
        for child in device.get("children", []):
            robots.extend(find_robots([child]))
    return robots


def get_component_value(components: list, cid: int):
    """Return reportedValue for a given component id, or None."""
    for c in components:
        if c.get("id") == cid:
            return c.get("reportedValue")
    return None


def format_ts(ts) -> str:
    if ts is None:
        return "—"
    try:
        dt = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts)


def print_robot_status(robot: dict, components: list):
    name = (robot.get("info") or {}).get("name") or robot.get("id", "unknown")
    sn = robot.get("sn", "—")
    device_id = robot.get("id", "—")
    sku = robot.get("sku", "—")
    vr = robot.get("vr", "—")
    connected = (robot.get("connectivity") or {}).get("connected", False)

    state_int = get_component_value(components, 15)
    state_label = ROBOT_STATE_INT.get(state_int, f"Unknown ({state_int})") if state_int is not None else "—"
    battery = get_component_value(components, 26)
    mode_int = get_component_value(components, 16)
    mode_label = next((label for name, (val, label) in CLEANING_MODES.items() if val == mode_int),
                      f"Idle ({mode_int})" if mode_int == 0 else f"Unknown ({mode_int})")
    pattern_int = get_component_value(components, 17)
    pattern_label = next((label for name, (val, label) in CLEANING_PATTERNS.items() if val == pattern_int), f"Unknown ({pattern_int})")
    last_clean_ts = get_component_value(components, 28)
    fw = get_component_value(components, 13)
    ip = get_component_value(components, 6)
    rssi = get_component_value(components, 5)
    alarms = robot.get("alarms") or []
    sched_time = get_component_value(components, 18)  # [0, hours, 0, duration] or similar
    multiday_sched = get_component_value(components, 36)  # {days, hours, minutes, duration}
    cycle_end = get_component_value(components, 31)  # 1 = last cycle ended

    print(f"\n{'─'*60}")
    print(f"  Robot   : {name}")
    print(f"  ID      : {device_id}")
    print(f"  S/N     : {sn}  SKU: {sku}  FW: {fw or vr}")
    print(f"  Cloud   : {'ONLINE' if connected else 'OFFLINE'}  IP: {ip or '—'}  RSSI: {rssi} dBm")
    print(f"  State   : {state_label}")
    print(f"  Battery : {battery}%")
    print(f"  Mode    : {mode_label}")
    print(f"  Pattern : {pattern_label}")
    print(f"  Last run: {last_clean_ts or '—'}  (cycle ended: {'yes' if cycle_end == 1 else 'no'})")

    if multiday_sched and isinstance(multiday_sched, dict):
        d = multiday_sched
        print(f"  Multiday: {d.get('days',0)}d  {d.get('hours',0):02d}:{d.get('minutes',0):02d}  duration={d.get('duration',0)} min")
    elif sched_time:
        print(f"  Schedule: {sched_time}")

    if alarms:
        print(f"  Alarms  : {len(alarms)} active")
        for a in alarms:
            print(f"            {a}")
    print(f"{'─'*60}")

    if "--verbose" in sys.argv or "-v" in sys.argv:
        print(f"\n  All components:")
        print(f"  {'ID':<5} {'Reported Value':<40} Last updated")
        print(f"  {'─'*5} {'─'*40} {'─'*25}")
        for comp in sorted(components, key=lambda c: c.get("id", 0)):
            cid = comp.get("id", "?")
            reported = json.dumps(comp.get("reportedValue")) if comp.get("reportedValue") is not None else "—"
            ts = format_ts(comp.get("ts"))
            print(f"  {cid:<5} {reported:<40} {ts}")


def pick_robot(robots: list, robot_index: int = 0) -> Optional[dict]:
    if not robots:
        return None
    if robot_index >= len(robots):
        print(f"Only {len(robots)} robot(s) found; index {robot_index} is out of range.", file=sys.stderr)
        return None
    return robots[robot_index]


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Control a Fluidra/Zodiac robot cleaner (Freedom Lite CI3102) via the cloud API."
    )
    p.add_argument("--email", default=os.environ.get("FLUIDRA_EMAIL"), help="Fluidra account email")
    p.add_argument("--password", default=os.environ.get("FLUIDRA_PASSWORD"), help="Fluidra account password")
    p.add_argument("--robot", type=int, default=0, metavar="INDEX",
                   help="Which robot to target if you have multiple (0-based, default: 0)")
    p.add_argument("--pool", type=int, default=None, metavar="INDEX",
                   help="Pool index to search (default: scan all pools)")
    p.add_argument("-v", "--verbose", action="store_true", help="Show all component values")

    actions = p.add_mutually_exclusive_group()
    actions.add_argument("--status", action="store_true", help="Print robot state (default action)")
    actions.add_argument("--list-pools", action="store_true", help="List all pools")
    actions.add_argument("--list-devices", action="store_true", help="List all devices in the pool(s)")
    actions.add_argument(
        "--mode", choices=list(CLEANING_MODES.keys()), metavar="MODE",
        help=f"Set cleaning mode. Options: {', '.join(CLEANING_MODES.keys())}"
    )
    actions.add_argument(
        "--pattern", choices=list(CLEANING_PATTERNS.keys()), metavar="PATTERN",
        help=f"Set cleaning pattern. Options: {', '.join(CLEANING_PATTERNS.keys())}"
    )
    actions.add_argument(
        "--set-component", nargs=2, metavar=("COMPONENT_ID", "VALUE"),
        help="Set a raw component value (VALUE parsed as JSON)."
    )
    return p


def resolve_robot(api: FluidraApi, args) -> tuple[Optional[dict], Optional[str], list]:
    """Returns (robot_device_dict, device_id, components)."""
    pools = api.get_pools()
    if not pools:
        print("No pools found on this account.", file=sys.stderr)
        return None, None, []

    pool_indices = [args.pool] if args.pool is not None else range(len(pools))

    for pool_idx in pool_indices:
        if pool_idx >= len(pools):
            print(f"Pool index {pool_idx} out of range (have {len(pools)}).", file=sys.stderr)
            continue
        pool = pools[pool_idx]
        pool_id = pool.get("id") or pool.get("poolId")
        devices = api.get_devices(pool_id)
        robots = find_robots(devices)
        if robots:
            robot = pick_robot(robots, args.robot)
            if robot is None:
                continue
            device_id = robot.get("id")
            print(f"Pool: {pool.get('name', pool_id)} (id={pool_id})")
            components = api.get_components(device_id)
            return robot, device_id, components

    print("No robot cleaner found in any pool.", file=sys.stderr)
    return None, None, []


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.email or not args.password:
        parser.error(
            "Credentials required. Set FLUIDRA_EMAIL and FLUIDRA_PASSWORD environment variables "
            "or pass --email / --password."
        )

    auth = CognitoAuth(args.email, args.password)
    api = FluidraApi(auth)

    # ── List pools ──────────────────────────────────────────────
    if args.list_pools:
        pools = api.get_pools()
        print(f"Found {len(pools)} pool(s):")
        for i, p in enumerate(pools):
            print(f"  [{i}] id={p.get('id')} name={p.get('name')}")
        return

    # ── List devices ────────────────────────────────────────────
    if args.list_devices:
        pools = api.get_pools()
        pool_indices = [args.pool] if args.pool is not None else range(len(pools))
        for pool_idx in pool_indices:
            if pool_idx >= len(pools):
                continue
            pool = pools[pool_idx]
            pool_id = pool.get("id") or pool.get("poolId")
            devices = api.get_devices(pool_id)
            print(f"\nPool [{pool_idx}] {pool.get('name', pool_id)} (id={pool_id}):")
            def print_tree(devs, indent=0):
                for d in devs:
                    name = (d.get("info") or {}).get("name") or "—"
                    family = (d.get("info") or {}).get("family") or d.get("deviceFamily") or "—"
                    robot_marker = " ★" if is_robot_cleaner(d) else ""
                    print(f"{'  '*indent}id={d.get('id')} family={family!r} type={d.get('type')} name={name!r}{robot_marker}")
                    print_tree(d.get("children", []), indent + 1)
            print_tree(devices)
        return

    # ── Robot actions ────────────────────────────────────────────
    robot, device_id, components = resolve_robot(api, args)
    if device_id is None:
        sys.exit(1)

    # Default: show status
    if args.status or (not any([args.mode, args.pattern, args.set_component])):
        print_robot_status(robot, components)
        return

    # ── Mode ──────────────────────────────────────────────────────
    if args.mode:
        value, label = CLEANING_MODES[args.mode]
        result = api.update_component(device_id, 16, value)
        print(f"Mode set to '{args.mode}' ({label}) → component 16 = {value}.")
        print(json.dumps(result, indent=2))

    # ── Pattern ───────────────────────────────────────────────────
    elif args.pattern:
        value, label = CLEANING_PATTERNS[args.pattern]
        result = api.update_component(device_id, 17, value)
        print(f"Pattern set to '{args.pattern}' ({label}) → component 17 = {value}.")
        print(json.dumps(result, indent=2))

    # ── Raw component set ─────────────────────────────────────────
    elif args.set_component:
        comp_id_str, raw_value = args.set_component
        comp_id = int(comp_id_str)
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            value = raw_value
        result = api.update_component(device_id, comp_id, value)
        print(f"Component {comp_id} set to {json.dumps(value)}.")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
