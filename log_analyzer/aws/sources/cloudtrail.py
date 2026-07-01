"""CloudTrail event fetching."""

import json
from datetime import datetime, timedelta, timezone

from ... import config
from ..client import client



def fetch_cloudtrail_events(
    hours: int = 24,
    event_name: str = "",
    username: str = "",
    max_events: int = config.DEFAULT_MAX_EVENTS,
    exclude_readonly_service_roles: bool = True,
    max_scan_events: int = 20000,
    profile: str | None = None,
    region: str | None = None,
    stats: dict | None = None,
) -> list[dict]:
    """Fetch recent CloudTrail management events via LookupEvents.

    Returns a list of simplified event dicts, oldest first. LookupEvents only
    covers the trailing 90 days and is eventually consistent (a few minutes
    of lag on very recent activity).

    By default, read-only events that AWS itself flags as service-initiated
    (CloudTrail's `userIdentity.invokedBy` field -- set whenever a service
    like Resource Explorer or RDS monitoring made the call, not a human or
    application principal) are skipped so they don't crowd out meaningful
    activity within `max_events`. These can generate thousands of events per
    day with zero security/cost relevance. Pass
    exclude_readonly_service_roles=False to disable this.

    `max_scan_events` bounds how many raw events LookupEvents will page
    through looking for matches, so a very noisy account with a wide `hours`
    window doesn't turn into an unbounded scan; if it's hit before
    `max_events` matches are found, the returned window won't reach all the
    way back to `hours` ago. If `stats` is passed (a dict), it's populated
    with {scanned, matched, hit_max_events, hit_scan_cap} so callers can
    report actual coverage.
    """
    ct = client("cloudtrail", profile, region)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    lookup_attrs = []
    if event_name:
        lookup_attrs.append({"AttributeKey": "EventName", "AttributeValue": event_name})
    elif username:
        lookup_attrs.append({"AttributeKey": "Username", "AttributeValue": username})

    kwargs = {"StartTime": start_time, "EndTime": end_time}
    if lookup_attrs:
        kwargs["LookupAttributes"] = lookup_attrs

    # If the caller explicitly asked for a specific username, respect that --
    # only apply the generic noise filter when browsing broadly.
    apply_noise_filter = exclude_readonly_service_roles and not username

    events: list[dict] = []
    scanned = 0

    def _finish(hit_max_events: bool, hit_scan_cap: bool) -> list[dict]:
        if stats is not None:
            stats.update(
                {
                    "scanned": scanned,
                    "matched": len(events),
                    "hit_max_events": hit_max_events,
                    "hit_scan_cap": hit_scan_cap,
                }
            )
        events.reverse()
        return events

    paginator = ct.get_paginator("lookup_events")
    for page in paginator.paginate(**kwargs):
        for e in page["Events"]:
            scanned += 1

            detail = {}
            raw = e.get("CloudTrailEvent")
            if raw:
                try:
                    detail = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    detail = {}

            invoked_by = detail.get("userIdentity", {}).get("invokedBy")
            is_noisy_readonly = e.get("ReadOnly") == "true" and bool(invoked_by)
            if apply_noise_filter and is_noisy_readonly:
                if scanned >= max_scan_events:
                    return _finish(hit_max_events=False, hit_scan_cap=True)
                continue

            events.append(
                {
                    "event_time": e["EventTime"].isoformat(),
                    "event_name": e.get("EventName"),
                    "event_source": e.get("EventSource"),
                    "username": e.get("Username"),
                    "read_only": e.get("ReadOnly"),
                    "invoked_by": invoked_by,
                    "aws_region": detail.get("awsRegion"),
                    "source_ip": detail.get("sourceIPAddress"),
                    "error_code": detail.get("errorCode"),
                    "error_message": detail.get("errorMessage"),
                    "resources": [r.get("ResourceName") for r in e.get("Resources", [])],
                }
            )

            if len(events) >= max_events:
                return _finish(hit_max_events=True, hit_scan_cap=False)
            if scanned >= max_scan_events:
                return _finish(hit_max_events=False, hit_scan_cap=True)

    return _finish(hit_max_events=False, hit_scan_cap=False)
