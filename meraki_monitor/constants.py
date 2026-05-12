"""Shared constants, column definitions, and color maps."""

MERAKI_BASE_URL = "https://api.meraki.com/api/v1"

BASE_COLUMNS: list[tuple[str, str]] = [
    ("name", "Name"),
    ("serial", "Serial"),
    ("model", "Model"),
    ("productType", "Product Type"),
    ("networkId", "Network ID"),
    ("mac", "MAC"),
    ("lanIp", "LAN IP"),
    ("publicIp", "Public IP"),
    ("firmware", "Firmware"),
    ("status", "Status"),
    ("lastReportedAt", "Last Reported"),
]

# Extra columns that can be toggled on/off via the Columns dialog.
# These fields come from the existing API responses at no extra cost.
EXTRA_COLUMNS: list[tuple[str, str]] = [
    ("alertCount", "Alerts"),
    ("address", "Location"),
    ("notes", "Notes"),
    ("tags", "Tags"),
    ("gateway", "Gateway"),
    ("ipType", "IP Type"),
    ("primaryDns", "Primary DNS"),
    ("secondaryDns", "Secondary DNS"),
    ("lat", "Latitude"),
    ("lng", "Longitude"),
    ("lastBootedAt", "Last Boot"),
]

# Active column list — starts with base only; mutated at runtime by MainWindow.
COLUMNS: list[tuple[str, str]] = list(BASE_COLUMNS)


def status_col_index() -> int:
    """Return the current column index of the 'status' field."""
    for i, (key, _) in enumerate(COLUMNS):
        if key == "status":
            return i
    return -1


PRODUCT_TYPES = [
    "wireless",
    "appliance",
    "switch",
    "camera",
    "cellularGateway",
    "sensor",
]

STATUS_COLORS: dict[str, str] = {
    "online": "#4CAF50",
    "alerting": "#FFC107",
    "offline": "#F44336",
    "dormant": "#9E9E9E",
}

SEVERITY_COLORS: dict[str, str] = {
    "critical": "#F44336",
    "warning": "#FFC107",
    "informational": "#2196F3",
    "info": "#2196F3",
}

SEVERITY_ORDER: dict[str, int] = {
    "critical": 0,
    "warning": 1,
    "informational": 2,
    "info": 2,
}

CADENCE_OPTIONS: list[tuple[str, int]] = [
    ("30s", 30_000),
    ("1m", 60_000),
    ("2m", 120_000),
    ("5m", 300_000),
]

DEFAULT_COLUMN_WIDTHS = [200, 140, 110, 110, 200, 140, 110, 110, 150, 100, 160]
