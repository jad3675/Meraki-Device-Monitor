# Meraki Device Monitor

A desktop troubleshooting and monitoring application for Cisco Meraki networks. Built with Python and PyQt6.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

## Features

### Devices Tab

- **Live device table** — view all devices in a Meraki organization with name, serial, model, product type, network ID, MAC, LAN/public IP, firmware, status, and last reported time.
- **Configurable extra columns** — toggle additional columns on or off via the Columns dialog:
  - Alert count, Location (physical address), Notes, Tags
  - Gateway, IP Type, Primary/Secondary DNS
  - Latitude, Longitude
  - Last Boot time (beta endpoint, MS switches only)
- **Status indicators** — color-coded status dots (green/online, yellow/alerting, red/offline, grey/dormant).
- **Filtering** — filter by product type, free-text search, or "Only with alerts" toggle.
- **Sorting** — click any column header to sort ascending/descending.
- **Auto-refresh** — configurable polling cadence (30s, 1m, 2m, 5m).
- **Health details** — double-click a device or select multiple rows and click "Health Details" to view network health alerts per device.
- **Timeline** — click "Timeline…" to view the full alert history for selected devices.
- **CSV export** — export the current filtered view to CSV.
- **Dark / Light theme** — toggle between themes with one click.

### Alerts Tab

- **Alert conditions view** — all active alert conditions across the org, grouped by severity/type/category, with device and network counts.
- **Multi-select alert groups** — select one or more alert conditions (Ctrl/Shift-click) to see the combined list of affected devices.
- **Severity filter** — dropdown to show only Critical, Warning, or Informational alerts.
- **Search** — free-text filter across alert type and category.
- **Affected devices pane** — shows devices impacted by the selected alert(s) with status indicators.
- **Show in Devices Tab** — jump to the Devices tab filtered to just the affected devices (with a clickable pill to clear the filter).
- **Show Timeline** — opens the alert timeline filtered to *only* the selected alert type(s) for the affected devices. Multi-select alert groups to see a combined timeline.
- **Alert count badge** — the Alerts tab shows a count badge when alerts are active.
- **CSV export** — export alert conditions with affected device details.

### Alert Timeline Dialog

- **Filtered by alert type** — when opened from the Alerts tab, only shows history entries matching the selected alert condition(s). When opened from the Devices tab, shows all alert types.
- **Chronological view** — columns: Occurred, Device, Serial, Alert Type, Details.
- **Sortable** — click column headers to re-sort (defaults to newest-first).
- **CSV export** — export the full timeline to CSV with all fields.

### Status Bar

- **Health summary** — real-time count of alerts, offline devices, and alerting devices (color-coded).
- **Device count** — shows visible/total device count when filters are active.
- **Filter pill** — when filtering by alert, a clickable pill shows the active filter and lets you clear it.

## Prerequisites

- Python 3.10 or later
- A [Cisco Meraki Dashboard API key](https://documentation.meraki.com/General_Administration/Other_Topics/Cisco_Meraki_Dashboard_API)
- Your Meraki Organization ID

## Installation

```bash
# Clone or download this repository
git clone <repo-url>
cd meraki-device-monitor

# (Recommended) Create a virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
python run.py
```

Or using the package directly:

```bash
python -m meraki_monitor
```

1. Enter your **API Key** and **Org ID** in the connection panel at the top.
2. Click **Fetch Devices** to load the device table and alerts.
3. Use the **Devices tab** to browse, filter, and export device data.
4. Switch to the **Alerts tab** to see active alert conditions grouped by type.
5. Select one or more alert conditions to see affected devices.
6. Click **Show Timeline…** to see when those specific alerts fired (filtered to just those alert types).
7. Click **Show in Devices Tab →** to jump back to the device list filtered to affected devices.
8. Use **Columns…** to enable extra columns (location, tags, last boot, alert count, etc.).
9. Enable **Auto-refresh** to keep data current.

## API Endpoints Used

| Endpoint | Purpose |
|---|---|
| `GET /organizations/{orgId}/devices` | Device inventory (name, model, serial, firmware, location, tags, notes, coordinates) |
| `GET /organizations/{orgId}/devices/statuses` | Live status, public IP, last reported time, gateway, DNS |
| `GET /organizations/{orgId}/devices/boots/history` | Last boot time (beta, MS switches only — degrades gracefully) |
| `GET /networks/{networkId}/health/alerts` | Active health alerts per network |
| `GET /networks/{networkId}/alerts/history` | Alert timeline / history (used by Timeline dialog) |

All requests include automatic pagination and rate-limit retry (respects `Retry-After` headers).

## Project Structure

```
├── meraki_monitor/            # Application package
│   ├── __init__.py            # Package entry point, exports main()
│   ├── __main__.py            # Enables `python -m meraki_monitor`
│   ├── constants.py           # Column defs, colors, cadences, URLs
│   ├── styles.py              # Dark/light Qt stylesheets
│   ├── utils.py               # Timestamp formatting, link parsing
│   ├── api.py                 # MerakiClient — API calls, pagination, retry
│   ├── workers.py             # Background QThread workers
│   ├── models.py              # Device table model + proxy filter model
│   ├── delegates.py           # StatusDelegate (colored status dots)
│   ├── health_dialog.py       # Health details dialog
│   ├── timeline_dialog.py     # Alert timeline dialog
│   ├── column_chooser.py      # Column chooser dialog
│   ├── alerts_tab.py          # Alerts tab (groups + affected devices)
│   └── app.py                 # MainWindow + main()
├── run.py                     # Top-level launcher script
├── requirements.txt           # Python dependencies
└── README.md
```

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| [PyQt6](https://pypi.org/project/PyQt6/) | ≥ 6.4.0 | Desktop GUI framework |
| [requests](https://pypi.org/project/requests/) | ≥ 2.28.0 | HTTP client for the Meraki Dashboard API |

## License

This project is provided as-is for internal/personal use. See your organization's policies regarding Meraki API usage and rate limits.
