"""Background QThread workers for API fetching."""

import threading

from PyQt6.QtCore import QThread, pyqtSignal

from meraki_monitor.api import MerakiAPIError, MerakiClient


class FetchWorker(QThread):
    """Fetches Meraki device data on a background thread."""

    data_ready = pyqtSignal(dict)
    error = pyqtSignal(str, int)
    progress = pyqtSignal(str)

    def __init__(self, api_key: str, org_id: str, parent=None):
        super().__init__(parent)
        self._api_key = api_key
        self._org_id = org_id
        self._stop = threading.Event()

    def cancel(self):
        self._stop.set()

    def run(self):
        try:
            client = MerakiClient(self._api_key, self._org_id)
            payload = client.fetch_all(self._stop, self.progress.emit)
            if not self._stop.is_set():
                self.data_ready.emit(payload)
        except MerakiAPIError as exc:
            if not self._stop.is_set():
                self.error.emit(str(exc), exc.status_code or -1)
        except Exception as exc:
            if not self._stop.is_set():
                self.error.emit(f"Unexpected error: {exc}", -1)


class HealthAlertWorker(QThread):
    """Fetches health alerts for selected devices on a background thread."""

    data_ready = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    def __init__(self, api_key: str, org_id: str, devices: list[dict], parent=None):
        super().__init__(parent)
        self._api_key = api_key
        self._org_id = org_id
        self._devices = devices
        self._stop = threading.Event()

    def cancel(self):
        self._stop.set()

    def run(self):
        try:
            client = MerakiClient(self._api_key, self._org_id)
            results = []
            network_alerts: dict[str, list[dict]] = {}
            network_ids = list({d.get("networkId", "") for d in self._devices if d.get("networkId")})
            total = len(network_ids)

            for i, net_id in enumerate(network_ids):
                if self._stop.is_set():
                    return
                self.progress.emit(i + 1, total)
                try:
                    alerts = client.fetch_health_alerts(net_id, self._stop)
                    network_alerts[net_id] = alerts
                except MerakiAPIError:
                    network_alerts[net_id] = []

            for device in self._devices:
                serial = device.get("serial", "")
                net_id = device.get("networkId", "")
                status = device.get("status", "")
                all_net_alerts = network_alerts.get(net_id, [])

                device_alerts = []
                for alert in all_net_alerts:
                    scope = alert.get("scope", {})
                    scope_devices = scope.get("devices", [])
                    device_match = False
                    if not scope_devices:
                        device_match = True
                    else:
                        for sd in scope_devices:
                            if sd.get("serial") == serial or sd.get("mac") == device.get("mac"):
                                device_match = True
                                break
                    if device_match:
                        device_alerts.append(alert)

                results.append({
                    "name": device.get("name", ""),
                    "serial": serial,
                    "model": device.get("model", ""),
                    "status": status,
                    "networkId": net_id,
                    "lanIp": device.get("lanIp", ""),
                    "publicIp": device.get("publicIp", ""),
                    "lastReportedAt": device.get("lastReportedAt", ""),
                    "alerts": device_alerts,
                })

            if not self._stop.is_set():
                self.data_ready.emit(results)
        except MerakiAPIError as exc:
            if not self._stop.is_set():
                self.error.emit(str(exc))
        except Exception as exc:
            if not self._stop.is_set():
                self.error.emit(f"Unexpected error: {exc}")


class TimelineWorker(QThread):
    """Fetches alert history for given networks and filters by device serials and alert types."""

    data_ready = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    def __init__(
        self,
        api_key: str,
        org_id: str,
        network_ids: list[str],
        serials: set[str] | None,
        alert_type_ids: set[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._api_key = api_key
        self._org_id = org_id
        self._network_ids = list(dict.fromkeys(network_ids))
        self._serials = set(serials) if serials else None
        self._alert_type_ids = set(alert_type_ids) if alert_type_ids else None
        self._stop = threading.Event()

    def cancel(self):
        self._stop.set()

    def run(self):
        try:
            client = MerakiClient(self._api_key, self._org_id)
            entries: list[dict] = []
            total = len(self._network_ids)

            for i, net_id in enumerate(self._network_ids):
                if self._stop.is_set():
                    return
                self.progress.emit(i + 1, total)
                try:
                    history = client.fetch_alert_history(net_id, self._stop)
                except MerakiAPIError:
                    history = []

                for entry in history:
                    serial = (entry.get("device") or {}).get("serial", "")
                    # Filter by serial if specified
                    if self._serials and serial not in self._serials:
                        continue
                    # Filter by alert type if specified
                    alert_type = entry.get("alertType", "") or ""
                    alert_type_id = entry.get("alertTypeId", "") or ""
                    if self._alert_type_ids:
                        if (alert_type not in self._alert_type_ids
                                and alert_type_id not in self._alert_type_ids):
                            continue
                    entries.append({
                        "occurredAt": entry.get("occurredAt", ""),
                        "alertType": alert_type or alert_type_id,
                        "alertTypeId": alert_type_id,
                        "serial": serial,
                        "networkId": net_id,
                        "alertData": entry.get("alertData", {}) or {},
                    })

            entries.sort(key=lambda e: e.get("occurredAt", ""), reverse=True)

            if not self._stop.is_set():
                self.data_ready.emit(entries)
        except MerakiAPIError as exc:
            if not self._stop.is_set():
                self.error.emit(str(exc))
        except Exception as exc:
            if not self._stop.is_set():
                self.error.emit(f"Unexpected error: {exc}")
