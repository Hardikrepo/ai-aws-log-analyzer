"""Azure provider: argparse wiring, analyze command, and chat tools."""

import argparse

from .. import cli_common
from . import config
from .sources.activity_log import fetch_activity_log_events

CHAT_SOURCES_DESCRIPTION = """Azure (--subscription-id):
- Activity Log (subscription-scoped control-plane activity -- who did what, from where)"""


# --------------------------------------------------------------------------
# `analyze azure <source>` commands
# --------------------------------------------------------------------------

def cmd_analyze_activity_log(args) -> None:
    events = fetch_activity_log_events(
        hours=args.hours,
        resource_group=args.resource_group or "",
        subscription_id=args.subscription_id,
    )
    adapted = [{"timestamp": e["event_time"], "message": str(e)} for e in events]
    cli_common.run_analysis("Azure Activity Log (account activity)", adapted, args)


# --------------------------------------------------------------------------
# chat tools
# --------------------------------------------------------------------------

CHAT_TOOLS = [
    {
        "name": "azure_get_activity_log",
        "description": (
            "Fetch recent Azure Activity Log events (subscription-scoped control-plane activity -- "
            "who did what, from where) for the last N hours."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hours": {"type": "integer", "description": "How many hours back to look. Default 24."},
                "resource_group": {
                    "type": "string",
                    "description": "Optional resource group name to filter to",
                },
            },
            "required": [],
        },
    },
]


def _execute_tool(name: str, tool_input: dict, args) -> str:
    if name == "azure_get_activity_log":
        events = fetch_activity_log_events(
            hours=tool_input.get("hours", 24),
            resource_group=tool_input.get("resource_group", ""),
            subscription_id=args.subscription_id,
        )
        adapted = [{"timestamp": e["event_time"], "message": str(e)} for e in events]
        return cli_common.format_events(adapted, max_chars=cli_common.CHAT_MAX_CHARS)

    return f"Unknown tool: {name}"


CHAT_DISPATCH = {tool["name"]: _execute_tool for tool in CHAT_TOOLS}


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------

def add_azure_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--subscription-id", default=config.DEFAULT_SUBSCRIPTION_ID, help="Azure subscription ID"
    )


def build_analyze_parser(provider_subparsers) -> None:
    azure_parser = provider_subparsers.add_parser("azure", help="Azure log sources")
    azure_sub = azure_parser.add_subparsers(dest="source", required=True)

    al = azure_sub.add_parser("activity-log", help="Analyze Azure Activity Log events")
    al.add_argument("--hours", type=int, default=24)
    al.add_argument("--resource-group", default=None)
    cli_common.add_mode_arg(al)
    add_azure_args(al)
    cli_common.add_model_effort_args(al)
    al.set_defaults(func=cmd_analyze_activity_log)
