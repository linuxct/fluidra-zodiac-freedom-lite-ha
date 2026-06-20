"""Constants for the Fluidra Robot Cleaner integration."""

DOMAIN = "fluidra_robot"

CONF_POOL_ID = "pool_id"
CONF_POOL_NAME = "pool_name"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"

SCAN_INTERVAL_SECONDS = 30

# Component 15: robot state (read-only — robot manages transitions)
ROBOT_STATE_INT: dict[int, str] = {
    0: "Submerge / Ready",
    1: "Cleaning",
    2: "Charging",
    3: "Charged (docked)",
    10: "Pick-up / Lift",
    11: "Offline",
}

# Component 16: cleaning mode (read-write)
CLEANING_MODE_OPTIONS = [
    "Floor & Walls",
    "Floor only",
    "Walls only",
    "Waterline only",
    "Multi-day",
]
CLEANING_MODE_LABEL_TO_INT: dict[str, int] = {
    "Floor & Walls": 1,
    "Floor only": 2,
    "Walls only": 3,
    "Waterline only": 4,
    "Multi-day": 5,
}
CLEANING_MODE_INT_TO_LABEL: dict[int, str] = {
    v: k for k, v in CLEANING_MODE_LABEL_TO_INT.items()
}

# Component 17: cleaning pattern (read-write)
CLEANING_PATTERN_OPTIONS = ["S-Pattern", "Standard"]
CLEANING_PATTERN_LABEL_TO_INT: dict[str, int] = {
    "S-Pattern": 0,
    "Standard": 1,
}
CLEANING_PATTERN_INT_TO_LABEL: dict[int, str] = {
    v: k for k, v in CLEANING_PATTERN_LABEL_TO_INT.items()
}
