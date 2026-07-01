"""GCP provider: argparse wiring, analyze command, and chat tools."""

import argparse

from .. import cli_common
from . import config
from .sources.cloud_logging import fetch_cloud_logging_entries

CHAT_SOURCES_DESCRIPTION = """GCP (--project):
- Cloud Logging (application/platform logs across all resource types in a project)"""


# --------------------------------------------------------------------------
# `analyze gcp <source>` commands
# --------------------------------------------------------------------------

def cmd_analyze_cloud_logging(args) -> None:
    events = fetch_cloud_logging_entries(
        hours=args.hours,
        filter_expression=args.filter or "",
        project=args.project,
    )
    cli_common.run_analysis(f"GCP Cloud Logging (project '{args.project or config.DEFAULT_PROJECT}')", events, args)


# --------------------------------------------------------------------------
# chat tools
# --------------------------------------------------------------------------

CHAT_TOOLS = [
    {
        "name": "gcp_get_cloud_logging_entries",
        "description": (
            "Fetch recent GCP Cloud Logging entries (application/platform logs across all "
            "resource types in a project) for the last N hours."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hours": {"type": "integer", "description": "How many hours back to look. Default 24."},
                "filter_expression": {
                    "type": "string",
                    "description": (
                        "Optional raw Cloud Logging Advanced Logs Filter fragment, e.g. "
                        '\'resource.type="cloud_run_revision" AND severity>=ERROR\'. ANDed with '
                        "the time window."
                    ),
                },
            },
            "required": [],
        },
    },
]


def _execute_tool(name: str, tool_input: dict, args) -> str:
    if name == "gcp_get_cloud_logging_entries":
        events = fetch_cloud_logging_entries(
            hours=tool_input.get("hours", 24),
            filter_expression=tool_input.get("filter_expression", ""),
            project=args.project,
        )
        return cli_common.format_events(events, max_chars=cli_common.CHAT_MAX_CHARS)

    return f"Unknown tool: {name}"


CHAT_DISPATCH = {tool["name"]: _execute_tool for tool in CHAT_TOOLS}


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------

def add_gcp_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", default=config.DEFAULT_PROJECT, help="GCP project ID")


def build_analyze_parser(provider_subparsers) -> None:
    gcp_parser = provider_subparsers.add_parser("gcp", help="GCP log sources")
    gcp_sub = gcp_parser.add_subparsers(dest="source", required=True)

    cl = gcp_sub.add_parser("cloud-logging", help="Analyze GCP Cloud Logging entries")
    cl.add_argument("--hours", type=int, default=24)
    cl.add_argument("--filter", default=None, help="Optional Cloud Logging Advanced Logs Filter fragment")
    cli_common.add_mode_arg(cl)
    add_gcp_args(cl)
    cli_common.add_model_effort_args(cl)
    cl.set_defaults(func=cmd_analyze_cloud_logging)
