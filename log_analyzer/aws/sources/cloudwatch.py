"""CloudWatch Logs fetching."""

import time

from ... import config
from ..client import client


def list_log_groups(prefix: str = "", profile: str | None = None, region: str | None = None) -> list[str]:
    logs = client("logs", profile, region)
    names: list[str] = []
    kwargs = {"logGroupNamePrefix": prefix} if prefix else {}
    paginator = logs.get_paginator("describe_log_groups")
    for page in paginator.paginate(**kwargs):
        names.extend(g["logGroupName"] for g in page["logGroups"])
    return names


def fetch_cloudwatch_logs(
    log_group: str,
    hours: int = 24,
    filter_pattern: str = "",
    max_events: int = config.DEFAULT_MAX_EVENTS,
    profile: str | None = None,
    region: str | None = None,
) -> list[dict]:
    """Fetch recent events from a CloudWatch Logs group.

    Returns a list of {timestamp, message} dicts, oldest first.
    """
    logs = client("logs", profile, region)
    start_ms = int((time.time() - hours * 3600) * 1000)

    kwargs = {
        "logGroupName": log_group,
        "startTime": start_ms,
        "interleaved": True,
    }
    if filter_pattern:
        kwargs["filterPattern"] = filter_pattern

    events: list[dict] = []
    paginator = logs.get_paginator("filter_log_events")
    for page in paginator.paginate(**kwargs):
        for e in page["events"]:
            events.append({"timestamp": e["timestamp"], "message": e["message"]})
            if len(events) >= max_events:
                events.sort(key=lambda x: x["timestamp"])
                return events

    events.sort(key=lambda x: x["timestamp"])
    return events
