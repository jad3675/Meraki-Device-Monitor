# Meraki Device Monitor

A desktop GUI application for monitoring Cisco Meraki devices across an organization. Built with Python and PyQt6.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

## Features

- **Live device table** — view all devices in a Meraki organization with name, serial, model, product type, network ID, MAC, LAN/public IP, firmware, status, and last reported time.
- **Configurable extra columns** — toggle additional columns on or off via the Columns dialog:
  - Location (physical address), Notes, Tags
  - Gateway, IP Type, Primary/Secondary DNS
  - Latitude, Longitude
  - Last Boot time (beta endpoint, MS switches only)
- **Status indicators** — color-coded status dots (green/online, yellow/alerting, red/offline, grey/dormant).
- **Filtering** — filter by product type (wireless, appliance, switch, camera, etc.) and free-text search across all fields.
- **Sorting** — click any column header to sort ascending/descending.
- **Auto-refresh** — configurable polling cadence (30s, 1m, 2m, 5m).
- **Health details** — double-click a device or select multiple rows and click "Health Details" to view network health alerts per device.
- **CSV export** — export the current filtered view or a health report to CSV.
- **Dark / Light theme** — toggle between themes with one click.

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
2. Click **Fetch Devices** to load the device table.
3. Use the **Filter** dropdown and search box to narrow results.
4. Click **Columns…** to enable extra columns (location, firmware, tags, last boot, etc.).
5. Enable **Auto-refresh** and pick a cadence to keep the data current.
6. Select rows and click **Health Details** to inspect network health alerts, or double-click any row.
7. Click **Export CSV** to save the current view.

## API Endpoints Used

| Endpoint | Purpose |
|---|---|
| `GET /organizations/{orgId}/devices` | Device inventory (name, model, serial, firmware, location, tags, notes, coordinates) |
| `GET /organizations/{orgId}/devices/statuses` | Live status, public IP, last reported time, gateway, DNS |
| `GET /organizations/{orgId}/devices/boots/history` | Last boot time (beta, MS switches only — degrades gracefully) |
| `GET /networks/{networkId}/health/alerts` | Network health alerts (used by Health Details dialog) |

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
