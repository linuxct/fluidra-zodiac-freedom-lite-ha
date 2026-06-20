# Fluidra Robot Cleaner for Home Assistant

A Home Assistant custom integration for **Zodiac Freedom Lite** and compatible Fluidra robot pool cleaners (CI3102 / N30L). Control and monitor your robot directly from Home Assistant via the Fluidra cloud API.

## Features

- Real-time robot state (cleaning, charging, docked, lifting, offline…)
- Battery level with native battery device class
- Cleaning mode and pattern selection (writable selects)
- Last clean timestamp
- Last seen timestamp (persisted across HA restarts)
- WiFi signal strength, IP address, firmware version
- Multi-day schedule info
- Connected / Cleaning / Charging binary sensors
- Full multi-robot support — add each robot as a separate integration entry

## Supported devices

Any robot cleaner paired to a Fluidra Pool account under the **Robot Cleaners** device family. Confirmed working on:

- Zodiac Freedom Lite CI3102

Other Fluidra / Zodiac / Polaris robot cleaners that use the same app may work too.

## Installation via HACS

1. Open HACS in Home Assistant.
2. Go to **Integrations → Custom repositories**.
3. Add `https://github.com/linuxct/fluidra-zodiac-freedom-lite-ha` as an **Integration**.
4. Search for **Fluidra Robot Cleaner** and install it.
5. Restart Home Assistant.

## Setup

Go to **Settings → Devices & Services → Add Integration** and search for **Fluidra Robot Cleaner**.

**Step 1 — Account login**

Enter the email and password you use to log in to the Fluidra Pool app.

**Step 2 — Select robot**

A dropdown lists every robot cleaner found across all your pools, labelled as `Pool Name → Robot Name`. Select the one you want to add.

Repeat the whole flow to add additional robots.

## Entities

### Sensors

| Entity | Description |
|---|---|
| State | Current robot state (Cleaning, Charging, Docked, Pick-up / Lift, Submerge / Ready, Offline) |
| Battery | Battery percentage |
| Last Clean | Timestamp of the last completed cleaning cycle |
| Last Seen | Last time HA observed the robot as connected (persisted across restarts) |
| Active Mode | Currently active cleaning mode |
| Active Pattern | Currently active cleaning pattern |
| Multi-day Schedule Days | Number of days configured for the multi-day schedule |
| Multi-day Schedule Duration | Duration per cycle in minutes |
| WiFi Signal | WiFi RSSI in dBm *(disabled by default)* |
| IP Address | Local IP address of the robot *(disabled by default)* |
| Firmware Version | Robot firmware version *(disabled by default)* |

### Binary Sensors

| Entity | Description |
|---|---|
| Connected | Whether the robot is reachable via the cloud |
| Cleaning | True while a cleaning cycle is running |
| Charging | True while the robot is on the charging dock |

### Select

| Entity | Options |
|---|---|
| Cleaning Mode | Floor & Walls, Floor only, Walls only, Waterline only, Multi-day |
| Cleaning Pattern | S-Pattern, Standard |

Changing a select writes the new value to the robot immediately.

## Notes

- The integration polls the Fluidra cloud every 30 seconds.
- Start / stop commands are not exposed. The robot starts a new cycle automatically when a cleaning mode is selected, consistent with how the official app works.
- Credentials are stored in Home Assistant's encrypted config entry storage.
