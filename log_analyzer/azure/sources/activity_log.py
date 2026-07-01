"""Azure Activity Log (subscription-scoped audit/control-plane events) fetching."""

from datetime import datetime, timedelta, timezone

from ... import config
from ..client import monitor_client


def _localized(value) -> str | None:
    """Activity Log fields like operation_name/status come back as LocalizableString
    objects (value + localized_value); reduce to a plain string."""
    if value is None:
        return None
    return getattr(value, "value", None) or str(value)


def fetch_activity_log_events(
    hours: int = 24,
    resource_group: str = "",
    max_events: int = config.DEFAULT_MAX_EVENTS,
    subscription_id: str | None = None,
) -> list[dict]:
    """Fetch recent Azure Activity Log events (who did what, at subscription scope).

    Returns a list of simplified event dicts, oldest first. Covers whatever
    retention the subscription has (typically 90 days).
    """
    client = monitor_client(subscription_id)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    filter_parts = [
        f"eventTimestamp ge '{start_time.isoformat()}'",
        f"eventTimestamp le '{end_time.isoformat()}'",
    ]
    if resource_group:
        filter_parts.append(f"resourceGroupName eq '{resource_group}'")
    filter_str = " and ".join(filter_parts)

    events: list[dict] = []
    for e in client.activity_logs.list(filter=filter_str):
        events.append(
            {
                "event_time": e.event_timestamp.isoformat() if e.event_timestamp else None,
                "operation_name": _localized(e.operation_name),
                "caller": e.caller,
                "status": _localized(e.status),
                "level": e.level,
                "resource_group": e.resource_group_name,
                "resource_id": e.resource_id,
            }
        )
        if len(events) >= max_events:
            break

    events.sort(key=lambda ev: ev["event_time"] or "")
    return events
