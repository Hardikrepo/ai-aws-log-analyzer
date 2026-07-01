"""S3 server access log fetching.

S3 access logging delivers plain-text log files (one or more request records
per line) into a target bucket/prefix. This module lists recently-delivered
log objects and returns their raw lines for analysis.
"""

from datetime import datetime, timedelta, timezone

from ... import config
from ..client import client


def fetch_s3_access_logs(
    bucket: str,
    prefix: str = "",
    hours: int = 24,
    max_events: int = config.DEFAULT_MAX_EVENTS,
    profile: str | None = None,
    region: str | None = None,
) -> list[dict]:
    """Fetch recent S3 access log lines from the given logging bucket/prefix.

    Returns a list of {timestamp, message} dicts (message = one raw access
    log line), oldest first, where timestamp is the log object's S3
    LastModified time (delivery time, not per-request time).
    """
    s3 = client("s3", profile, region)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    lines: list[dict] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["LastModified"] < cutoff:
                continue
            body = s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
            ts = obj["LastModified"].isoformat()
            for raw_line in body.decode("utf-8", errors="replace").splitlines():
                if not raw_line.strip():
                    continue
                lines.append({"timestamp": ts, "message": raw_line})
                if len(lines) >= max_events:
                    return lines

    return lines
