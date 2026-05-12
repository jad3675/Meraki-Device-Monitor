"""Small utility functions shared across modules."""

import re
from datetime import datetime


def parse_next_link(link_header: str) -> str | None:
    """Parse RFC 5988 Link header and return the 'next' URL, or None."""
    if not link_header:
        return None
    for part in link_header.split(","):
        part = part.strip()
        if 'rel="next"' in part or "rel=next" in part:
            match = re.search(r"<([^>]+)>", part)
            if match:
                return match.group(1)
    return None


def format_timestamp(iso_str: str | None) -> str:
    """Convert ISO 8601 timestamp to local human-friendly string."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        local_dt = dt.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return str(iso_str)


def summarize_alert_data(data: dict) -> str:
    """Render alertData dict as a compact human-readable string."""
    if not isinstance(data, dict) or not data:
        return ""
    parts = []
    for k, v in data.items():
        if isinstance(v, (dict, list)):
            continue
        parts.append(f"{k}={v}")
    return ", ".join(parts)
