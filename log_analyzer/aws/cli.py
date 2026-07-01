"""AWS provider: argparse wiring, analyze/list commands, and chat tools."""

import argparse

from .. import cli_common
from . import config
from .sources.cloudtrail import fetch_cloudtrail_events
from .sources.cloudwatch import fetch_cloudwatch_logs, list_log_groups
from .sources.s3_access_logs import fetch_s3_access_logs
from .sources.vpc_flow_logs import fetch_vpc_flow_logs, list_flow_log_groups

CHAT_SOURCES_DESCRIPTION = """AWS (--profile/--region):
- CloudWatch Logs (application/Lambda/service logs)
- CloudTrail (account API activity -- who did what, from where)
- VPC Flow Logs (network traffic accepted/rejected at the ENI level, delivered via CloudWatch Logs)
- S3 server access logs (per-request access logs delivered to a logging bucket)"""


# --------------------------------------------------------------------------
# `analyze aws <source>` commands
# --------------------------------------------------------------------------

def cmd_analyze_cloudwatch(args) -> None:
    events = fetch_cloudwatch_logs(
        log_group=args.log_group,
        hours=args.hours,
        filter_pattern=args.filter_pattern or "",
        profile=args.profile,
        region=args.region,
    )
    cli_common.run_analysis(f"CloudWatch Logs group '{args.log_group}'", events, args)


def cmd_analyze_cloudtrail(args) -> None:
    stats: dict = {}
    events = fetch_cloudtrail_events(
        hours=args.hours,
        event_name=args.event_name or "",
        username=args.username or "",
        exclude_readonly_service_roles=not args.include_service_noise,
        profile=args.profile,
        region=args.region,
        stats=stats,
    )

    if events:
        print(f"Coverage: {events[0]['event_time']} .. {events[-1]['event_time']}")
    if stats.get("hit_scan_cap"):
        print(
            f"Note: stopped after scanning {stats['scanned']} raw events (scan cap) -- "
            f"this did not reach all the way back to the requested {args.hours}h window. "
            "Narrow --hours or use --event-name/--username to see further back."
        )
    elif stats.get("hit_max_events"):
        from .. import config as common_config

        print(
            f"Note: hit the {common_config.DEFAULT_MAX_EVENTS}-event analysis cap before reaching "
            f"the full requested {args.hours}h window -- results reflect the most recent "
            "matching activity only."
        )

    # CloudTrail events are dicts, not {timestamp, message} -- adapt for format_events.
    adapted = [{"timestamp": e["event_time"], "message": str(e)} for e in events]
    cli_common.run_analysis("CloudTrail (account activity)", adapted, args)


def cmd_analyze_vpc_flow_logs(args) -> None:
    events = fetch_vpc_flow_logs(
        log_group=args.log_group,
        hours=args.hours,
        filter_pattern=args.filter_pattern or "",
        profile=args.profile,
        region=args.region,
    )
    cli_common.run_analysis(f"VPC Flow Logs group '{args.log_group}'", events, args)


def cmd_analyze_s3_access_logs(args) -> None:
    events = fetch_s3_access_logs(
        bucket=args.bucket,
        prefix=args.prefix or "",
        hours=args.hours,
        profile=args.profile,
        region=args.region,
    )
    cli_common.run_analysis(f"S3 access logs (bucket '{args.bucket}')", events, args)


# --------------------------------------------------------------------------
# `list aws <what>` commands
# --------------------------------------------------------------------------

def cmd_list_log_groups(args) -> None:
    for name in list_log_groups(prefix=args.prefix or "", profile=args.profile, region=args.region):
        print(name)


def cmd_list_flow_logs(args) -> None:
    for fl in list_flow_log_groups(profile=args.profile, region=args.region):
        print(fl)


# --------------------------------------------------------------------------
# chat tools
# --------------------------------------------------------------------------

CHAT_TOOLS = [
    {
        "name": "aws_list_log_groups",
        "description": (
            "List CloudWatch Logs group names, optionally filtered by prefix. "
            "Use this to discover the exact log group name before fetching from it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"prefix": {"type": "string", "description": "Optional name prefix filter"}},
            "required": [],
        },
    },
    {
        "name": "aws_get_cloudwatch_logs",
        "description": (
            "Fetch recent events from an AWS CloudWatch Logs group (application/Lambda/service logs). "
            "Call aws_list_log_groups first if you don't know the exact log group name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "log_group": {"type": "string", "description": "Exact CloudWatch Logs group name"},
                "hours": {"type": "integer", "description": "How many hours back to look. Default 24."},
                "filter_pattern": {
                    "type": "string",
                    "description": "Optional CloudWatch Logs filter pattern, e.g. 'ERROR'",
                },
            },
            "required": ["log_group"],
        },
    },
    {
        "name": "aws_get_cloudtrail_events",
        "description": (
            "Fetch recent AWS CloudTrail account activity (API calls, console logins, IAM changes, "
            "etc.) for the last N hours. Covers up to the trailing 90 days. By default, read-only "
            "AWS service-linked-role noise (Resource Explorer indexing, RDS monitoring, etc.) is "
            "excluded so a wide time window isn't consumed by automated background activity -- the "
            "result text will note if the requested window wasn't fully covered."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hours": {"type": "integer", "description": "How many hours back to look. Default 24."},
                "event_name": {"type": "string", "description": "Optional exact CloudTrail event name filter"},
                "username": {"type": "string", "description": "Optional exact IAM username filter"},
                "include_service_noise": {
                    "type": "boolean",
                    "description": (
                        "Set true to include read-only AWS service-linked-role activity that's "
                        "excluded by default. Only useful if you specifically need to inspect that noise."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "aws_list_vpc_flow_logs",
        "description": (
            "List configured VPC Flow Logs and their CloudWatch Logs destinations. Use this to "
            "discover the log group name before fetching flow log records."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "aws_get_vpc_flow_logs",
        "description": (
            "Fetch recent VPC Flow Log records (network traffic accepted/rejected at the ENI level) "
            "from a CloudWatch Logs group. Call aws_list_vpc_flow_logs first to find the log group name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "log_group": {"type": "string", "description": "CloudWatch Logs group receiving the flow logs"},
                "hours": {"type": "integer", "description": "How many hours back to look. Default 24."},
                "filter_pattern": {"type": "string", "description": "Optional CloudWatch Logs filter pattern"},
            },
            "required": ["log_group"],
        },
    },
    {
        "name": "aws_get_s3_access_logs",
        "description": "Fetch recent S3 server access log lines (per-request access records) from a logging bucket/prefix.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bucket": {"type": "string", "description": "S3 bucket that receives the access logs"},
                "prefix": {"type": "string", "description": "Optional key prefix for the access logs"},
                "hours": {"type": "integer", "description": "How many hours back to look. Default 24."},
            },
            "required": ["bucket"],
        },
    },
]


def _execute_tool(name: str, tool_input: dict, args) -> str:
    profile, region = args.profile, args.region

    if name == "aws_list_log_groups":
        names = list_log_groups(prefix=tool_input.get("prefix", ""), profile=profile, region=region)
        return "\n".join(names) if names else "(no log groups found)"

    if name == "aws_get_cloudwatch_logs":
        events = fetch_cloudwatch_logs(
            log_group=tool_input["log_group"],
            hours=tool_input.get("hours", 24),
            filter_pattern=tool_input.get("filter_pattern", ""),
            profile=profile,
            region=region,
        )
        return cli_common.format_events(events, max_chars=cli_common.CHAT_MAX_CHARS)

    if name == "aws_get_cloudtrail_events":
        stats: dict = {}
        events = fetch_cloudtrail_events(
            hours=tool_input.get("hours", 24),
            event_name=tool_input.get("event_name", ""),
            username=tool_input.get("username", ""),
            exclude_readonly_service_roles=not tool_input.get("include_service_noise", False),
            profile=profile,
            region=region,
            stats=stats,
        )
        adapted = [{"timestamp": e["event_time"], "message": str(e)} for e in events]
        text = cli_common.format_events(adapted, max_chars=cli_common.CHAT_MAX_CHARS)

        coverage = ""
        if events:
            coverage = f"Coverage: {events[0]['event_time']} .. {events[-1]['event_time']}\n"
        if stats.get("hit_scan_cap"):
            coverage += (
                f"NOTE: stopped after scanning {stats['scanned']} raw events (scan cap) -- this "
                f"did NOT reach all the way back to the requested {tool_input.get('hours', 24)}h "
                "window. Tell the user the result covers less history than requested.\n"
            )
        elif stats.get("hit_max_events"):
            coverage += (
                f"NOTE: hit the analysis event cap before reaching the full requested "
                f"{tool_input.get('hours', 24)}h window -- this reflects only the most recent "
                "matching activity. Tell the user coverage is partial.\n"
            )
        return coverage + text

    if name == "aws_list_vpc_flow_logs":
        flow_logs = list_flow_log_groups(profile=profile, region=region)
        return "\n".join(str(fl) for fl in flow_logs) if flow_logs else "(no VPC flow logs configured)"

    if name == "aws_get_vpc_flow_logs":
        events = fetch_vpc_flow_logs(
            log_group=tool_input["log_group"],
            hours=tool_input.get("hours", 24),
            filter_pattern=tool_input.get("filter_pattern", ""),
            profile=profile,
            region=region,
        )
        return cli_common.format_events(events, max_chars=cli_common.CHAT_MAX_CHARS)

    if name == "aws_get_s3_access_logs":
        events = fetch_s3_access_logs(
            bucket=tool_input["bucket"],
            prefix=tool_input.get("prefix", ""),
            hours=tool_input.get("hours", 24),
            profile=profile,
            region=region,
        )
        return cli_common.format_events(events, max_chars=cli_common.CHAT_MAX_CHARS)

    return f"Unknown tool: {name}"


CHAT_DISPATCH = {tool["name"]: _execute_tool for tool in CHAT_TOOLS}


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------

def add_aws_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", default=None, help="AWS CLI profile to use")
    parser.add_argument("--region", default=config.DEFAULT_REGION, help="AWS region")


def build_analyze_parser(provider_subparsers) -> None:
    aws_parser = provider_subparsers.add_parser("aws", help="AWS log sources")
    aws_sub = aws_parser.add_subparsers(dest="source", required=True)

    cw = aws_sub.add_parser("cloudwatch", help="Analyze a CloudWatch Logs group")
    cw.add_argument("--log-group", required=True)
    cw.add_argument("--hours", type=int, default=24)
    cw.add_argument("--filter-pattern", default=None)
    cli_common.add_mode_arg(cw)
    add_aws_args(cw)
    cli_common.add_model_effort_args(cw)
    cw.set_defaults(func=cmd_analyze_cloudwatch)

    ct = aws_sub.add_parser("cloudtrail", help="Analyze CloudTrail account activity")
    ct.add_argument("--hours", type=int, default=24)
    ct.add_argument("--event-name", default=None)
    ct.add_argument("--username", default=None)
    ct.add_argument(
        "--include-service-noise",
        action="store_true",
        help=(
            "Include read-only AWS service-linked-role activity (Resource Explorer indexing, "
            "RDS monitoring, etc.) that's excluded by default to keep wide time windows from "
            "being eaten by automated noise."
        ),
    )
    cli_common.add_mode_arg(ct)
    add_aws_args(ct)
    cli_common.add_model_effort_args(ct)
    ct.set_defaults(func=cmd_analyze_cloudtrail)

    vpc = aws_sub.add_parser("vpc-flow-logs", help="Analyze VPC Flow Logs")
    vpc.add_argument("--log-group", required=True)
    vpc.add_argument("--hours", type=int, default=24)
    vpc.add_argument("--filter-pattern", default=None)
    cli_common.add_mode_arg(vpc)
    add_aws_args(vpc)
    cli_common.add_model_effort_args(vpc)
    vpc.set_defaults(func=cmd_analyze_vpc_flow_logs)

    s3l = aws_sub.add_parser("s3-access-logs", help="Analyze S3 server access logs")
    s3l.add_argument("--bucket", required=True)
    s3l.add_argument("--prefix", default=None)
    s3l.add_argument("--hours", type=int, default=24)
    cli_common.add_mode_arg(s3l)
    add_aws_args(s3l)
    cli_common.add_model_effort_args(s3l)
    s3l.set_defaults(func=cmd_analyze_s3_access_logs)


def build_list_parser(provider_subparsers) -> None:
    aws_parser = provider_subparsers.add_parser("aws", help="AWS discovery helpers")
    aws_sub = aws_parser.add_subparsers(dest="what", required=True)

    lg = aws_sub.add_parser("log-groups", help="List CloudWatch Logs group names")
    lg.add_argument("--prefix", default=None)
    add_aws_args(lg)
    lg.set_defaults(func=cmd_list_log_groups)

    lf = aws_sub.add_parser("flow-logs", help="List configured VPC Flow Logs")
    add_aws_args(lf)
    lf.set_defaults(func=cmd_list_flow_logs)
