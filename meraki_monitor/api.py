"""Meraki Dashboard API v1 client with pagination and rate-limit retry."""

import threading
import time

import requests

from meraki_monitor.constants import MERAKI_BASE_URL
from meraki_monitor.utils import parse_next_link


class MerakiAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class MerakiClient:
    """Handles Meraki Dashboard API v1 requests with pagination and rate-limit retry."""

    def __init__(self, api_key: str, org_id: str):
        self._org_id = org_id
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    def _get_with_retry(
        self, url: str, params: dict | None = None, retries: int = 3
    ) -> requests.Response:
        for attempt in range(retries):
            try:
                resp = self._session.get(url, params=params, timeout=30)
            except requests.ConnectionError:
                raise MerakiAPIError(
                    "Cannot reach api.meraki.com. Check your network connection."
                )
            except requests.Timeout:
                raise MerakiAPIError("Request timed out (30s). Check connectivity.")

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                time.sleep(retry_after + 0.1)
                continue

            if resp.status_code == 401:
                raise MerakiAPIError(
                    "Authentication failed: invalid API key.", 401
                )
            if resp.status_code == 403:
                raise MerakiAPIError(
                    "Access denied: check your Org ID and API key permissions.", 403
                )
            if resp.status_code == 404:
                raise MerakiAPIError(
                    "Organization not found. Verify your Org ID.", 404
                )
            if not resp.ok:
                body = resp.text[:300] if resp.text else "No details"
                raise MerakiAPIError(
                    f"API error {resp.status_code}: {body}", resp.status_code
                )

            return resp

        raise MerakiAPIError("Rate limited after multiple retries.", 429)

    def _get_paginated(
        self,
        url: str,
        per_page: int,
        stop_event: threading.Event,
    ) -> list[dict]:
        results: list[dict] = []
        params: dict = {"perPage": per_page}
        current_url = url

        while current_url:
            if stop_event.is_set():
                return results

            resp = self._get_with_retry(current_url, params)
            page_data = resp.json()

            if isinstance(page_data, list):
                results.extend(page_data)
            else:
                results.append(page_data)

            current_url = parse_next_link(resp.headers.get("Link", ""))
            params = {}

        return results

    def fetch_devices(self, stop_event: threading.Event) -> list[dict]:
        url = f"{MERAKI_BASE_URL}/organizations/{self._org_id}/devices"
        return self._get_paginated(url, 1000, stop_event)

    def fetch_networks(self, stop_event: threading.Event) -> list[dict]:
        """Fetch all networks in the organization."""
        url = f"{MERAKI_BASE_URL}/organizations/{self._org_id}/networks"
        return self._get_paginated(url, 1000, stop_event)

    def fetch_statuses(self, stop_event: threading.Event) -> list[dict]:
        url = f"{MERAKI_BASE_URL}/organizations/{self._org_id}/devices/statuses"
        return self._get_paginated(url, 1000, stop_event)

    def fetch_boot_history(self, stop_event: threading.Event) -> list[dict]:
        """Fetch most recent boot per device (beta, MS-only)."""
        url = f"{MERAKI_BASE_URL}/organizations/{self._org_id}/devices/boots/history"
        try:
            return self._get_paginated(url, 1000, stop_event)
        except MerakiAPIError:
            return []

    def fetch_health_alerts(
        self,
        network_id: str,
        stop_event: threading.Event,
    ) -> list[dict]:
        """Fetch health alerts for a specific network."""
        if stop_event.is_set():
            return []
        url = f"{MERAKI_BASE_URL}/networks/{network_id}/health/alerts"
        resp = self._get_with_retry(url)
        data = resp.json()
        return data if isinstance(data, list) else []

    def fetch_alert_history(
        self,
        network_id: str,
        stop_event: threading.Event,
        max_pages: int = 5,
    ) -> list[dict]:
        """Fetch alert history (timeline) for a specific network."""
        if stop_event.is_set():
            return []
        url = f"{MERAKI_BASE_URL}/networks/{network_id}/alerts/history"
        results: list[dict] = []
        params: dict = {"perPage": 1000}
        current_url = url
        pages = 0

        while current_url and pages < max_pages:
            if stop_event.is_set():
                return results
            resp = self._get_with_retry(current_url, params)
            page_data = resp.json()
            if isinstance(page_data, list):
                results.extend(page_data)
            current_url = parse_next_link(resp.headers.get("Link", ""))
            params = {}
            pages += 1

        return results

    def fetch_all(
        self,
        stop_event: threading.Event,
        progress_cb=None,
    ) -> dict:
        """Fetch devices, statuses, boot history, and health alerts.

        Returns {"devices": [...], "alerts_by_network": {netId: [alerts]}}.
        """
        if progress_cb:
            progress_cb("Fetching devices...")
        devices = self.fetch_devices(stop_event)
        if stop_event.is_set():
            return {"devices": [], "alerts_by_network": {}}

        if progress_cb:
            progress_cb(f"Found {len(devices)} devices. Fetching statuses...")
        statuses = self.fetch_statuses(stop_event)
        if stop_event.is_set():
            return {"devices": [], "alerts_by_network": {}}

        status_map = {s["serial"]: s for s in statuses}
        for device in devices:
            entry = status_map.get(device.get("serial", ""), {})
            device["status"] = entry.get("status", "")
            device["publicIp"] = entry.get("publicIp", "")
            device["lastReportedAt"] = entry.get("lastReportedAt", "")
            device["gateway"] = entry.get("gateway", "")
            device["ipType"] = entry.get("ipType", "")
            device["primaryDns"] = entry.get("primaryDns", "")
            device["secondaryDns"] = entry.get("secondaryDns", "")
            tags = device.get("tags")
            if isinstance(tags, list):
                device["tags"] = ", ".join(tags)

        # Fetch network names
        if progress_cb:
            progress_cb("Fetching network names...")
        try:
            networks = self.fetch_networks(stop_event)
        except MerakiAPIError:
            networks = []
        if stop_event.is_set():
            return {"devices": [], "alerts_by_network": {}}

        network_name_map = {n.get("id", ""): n.get("name", "") for n in networks}
        for device in devices:
            device["networkName"] = network_name_map.get(device.get("networkId", ""), "")

        if progress_cb:
            progress_cb("Fetching boot history...")
        boots = self.fetch_boot_history(stop_event)
        if stop_event.is_set():
            return {"devices": [], "alerts_by_network": {}}

        boot_map: dict[str, str] = {}
        for entry in boots:
            serial = entry.get("serial", "")
            booted_at = (entry.get("start") or {}).get("bootedAt", "")
            if serial and booted_at and serial not in boot_map:
                boot_map[serial] = booted_at
        for device in devices:
            device["lastBootedAt"] = boot_map.get(device.get("serial", ""), "")

        network_ids = list({d.get("networkId", "") for d in devices if d.get("networkId")})
        alerts_by_network: dict[str, list[dict]] = {}
        total_nets = len(network_ids)
        for i, net_id in enumerate(network_ids):
            if stop_event.is_set():
                return {"devices": [], "alerts_by_network": {}}
            if progress_cb:
                progress_cb(f"Fetching alerts... ({i + 1}/{total_nets} networks)")
            try:
                alerts_by_network[net_id] = self.fetch_health_alerts(net_id, stop_event)
            except MerakiAPIError:
                alerts_by_network[net_id] = []

        for device in devices:
            net_id = device.get("networkId", "")
            serial = device.get("serial", "")
            mac = device.get("mac", "")
            net_alerts = alerts_by_network.get(net_id, [])
            matched: list[dict] = []
            for alert in net_alerts:
                scope = alert.get("scope", {}) or {}
                scope_devices = scope.get("devices", []) or []
                if not scope_devices:
                    matched.append(alert)
                    continue
                for sd in scope_devices:
                    if sd.get("serial") == serial or (mac and sd.get("mac") == mac):
                        matched.append(alert)
                        break
            device["alerts"] = matched
            device["alertCount"] = len(matched)

        if progress_cb:
            progress_cb(f"Loaded {len(devices)} devices.")

        return {"devices": devices, "alerts_by_network": alerts_by_network}
