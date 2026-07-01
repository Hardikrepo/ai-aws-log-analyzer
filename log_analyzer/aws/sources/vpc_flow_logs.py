"""VPC Flow Logs fetching (CloudWatch Logs destination)."""

from ... import config
from ..client import client
from .cloudwatch import fetch_cloudwatch_logs


def list_flow_log_groups(profile: str | None = None, region: str | None = None) -> list[dict]:
    """List configured VPC Flow Logs and their CloudWatch Logs destinations."""
    ec2 = client("ec2", profile, region)
    flow_logs = ec2.describe_flow_logs()["FlowLogs"]
    return [
        {
            "flow_log_id": fl["FlowLogId"],
            "resource_id": fl.get("ResourceId"),
            "log_destination_type": fl.get("LogDestinationType"),
            "log_group_name": fl.get("LogGroupName"),
            "log_destination": fl.get("LogDestination"),
        }
        for fl in flow_logs
    ]


def fetch_vpc_flow_logs(
    log_group: str,
    hours: int = 24,
    filter_pattern: str = "",
    max_events: int = config.DEFAULT_MAX_EVENTS,
    profile: str | None = None,
    region: str | None = None,
) -> list[dict]:
    """Fetch recent VPC Flow Log records from a CloudWatch Logs group.

    Flow log records are space-delimited text pushed into CloudWatch Logs;
    this returns the same {timestamp, message} shape as fetch_cloudwatch_logs
    so callers can reuse the same downstream parsing/analysis.
    """
    return fetch_cloudwatch_logs(
        log_group=log_group,
        hours=hours,
        filter_pattern=filter_pattern,
        max_events=max_events,
        profile=profile,
        region=region,
    )
