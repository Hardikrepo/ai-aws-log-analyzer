"""GCP Cloud Logging fetching."""

from datetime import datetime, timedelta, timezone

import google.cloud.logging

from ... import config
from ..client import logging_client


def fetch_cloud_logging_entries(
    hours: int = 24,
    filter_expression: str = "",
    max_events: int = config.DEFAULT_MAX_EVENTS,
    project: str | None = None,
) -> list[dict]:
    """Fetch recent Cloud Logging entries.

    Returns a list of {timestamp, message} dicts, oldest first -- the same
    shape fetch_cloudwatch_logs uses, so format_events() needs no adapter.
    `filter_expression` is an optional raw Advanced Logs Filter fragment
    (e.g. 'resource.type="cloud_run_revision" AND severity>=ERROR'), ANDed
    with the time window.
    """
    client = logging_client(project)
    start = datetime.now(timezone.utc) - timedelta(hours=hours)

    filter_parts = [f'timestamp>="{start.isoformat()}"']
    if filter_expression:
        filter_parts.append(f"({filter_expression})")
    filter_str = " AND ".join(filter_parts)

    entries: list[dict] = []
    iterator = client.list_entries(
        filter_=filter_str,
        order_by=google.cloud.logging.ASCENDING,
        page_size=min(max_events, 1000),
    )
    for entry in iterator:
        payload = entry.payload
        message = payload if isinstance(payload, str) else str(payload)
        if entry.severity:
            message = f"[{entry.severity}] {message}"
        entries.append({"timestamp": entry.timestamp, "message": message})
        if len(entries) >= max_events:
            break

    return entries
