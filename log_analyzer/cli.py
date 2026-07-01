"""AI-powered multi-cloud log analyzer -- CLI entry point."""

import argparse
import json
import sys

from . import cli_common, config
from .analysis import anthropic_client, openai_client, prompts
from .aws import cli as aws_cli
from .azure import cli as azure_cli
from .gcp import cli as gcp_cli

# Providers that expose an `analyze`/`chat` surface. GCP/Azure don't have a
# `list` (discovery) command yet -- only AWS does, see build_list_parser below.
PROVIDER_MODULES = {"aws": aws_cli, "gcp": gcp_cli, "azure": azure_cli}


# --------------------------------------------------------------------------
# `chat` subcommand -- agentic natural-language interface over all providers
# --------------------------------------------------------------------------

def _to_openai_tools(tools: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]},
        }
        for t in tools
    ]


def _run_anthropic_chat(tools: list[dict], dispatch: dict, system_prompt: str, model: str, args) -> None:
    client = anthropic_client.get_client()
    messages: list[dict] = []

    print("Multi-cloud log analyzer chat (Anthropic backend). Ask about your logs in plain English. Type 'exit' to quit.\n")

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break

        messages.append({"role": "user", "content": user_input})

        while True:
            kwargs = {
                "model": model,
                "max_tokens": config.DEFAULT_MAX_TOKENS,
                "system": system_prompt,
                "tools": tools,
                "messages": messages,
            }
            if "haiku" not in model:
                kwargs["thinking"] = {"type": "adaptive"}
                kwargs["output_config"] = {"effort": args.effort}

            response = client.messages.create(**kwargs)
            messages.append({"role": "assistant", "content": response.content})

            for block in response.content:
                if block.type == "text" and block.text:
                    print(f"\nanthropic> {block.text}\n")

            if response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                print(f"  [calling {block.name}({block.input})]")
                try:
                    result_text = dispatch[block.name](block.name, block.input, args)
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": result_text}
                    )
                except Exception as exc:  # noqa: BLE001 -- surface any cloud/tool error to the model
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Error: {exc}",
                            "is_error": True,
                        }
                    )

            messages.append({"role": "user", "content": tool_results})


def _run_openai_chat(tools: list[dict], dispatch: dict, system_prompt: str, model: str, args) -> None:
    client = openai_client.get_client()
    openai_tools = _to_openai_tools(tools)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    print("Multi-cloud log analyzer chat (OpenAI backend). Ask about your logs in plain English. Type 'exit' to quit.\n")

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break

        messages.append({"role": "user", "content": user_input})

        while True:
            kwargs = {"model": model, "messages": messages, "tools": openai_tools}
            if openai_client.supports_reasoning_effort(model):
                kwargs["reasoning_effort"] = openai_client.map_effort(args.effort)

            response = client.chat.completions.create(**kwargs)
            msg = response.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))

            if msg.content:
                print(f"\ngpt> {msg.content}\n")

            if not msg.tool_calls:
                break

            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    tool_input = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    tool_input = {}
                print(f"  [calling {name}({tool_input})]")
                try:
                    result_text = dispatch[name](name, tool_input, args)
                except Exception as exc:  # noqa: BLE001 -- surface any cloud/tool error to the model
                    result_text = f"Error: {exc}"
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_text})


def cmd_chat(args) -> None:
    provider_names = [args.provider] if args.provider else list(PROVIDER_MODULES)
    modules = [PROVIDER_MODULES[name] for name in provider_names]

    tools: list[dict] = []
    dispatch: dict = {}
    for mod in modules:
        tools.extend(mod.CHAT_TOOLS)
        dispatch.update(mod.CHAT_DISPATCH)

    available_sources = "\n\n".join(mod.CHAT_SOURCES_DESCRIPTION for mod in modules)
    system_prompt = prompts.CHAT_SYSTEM_PROMPT.format(available_sources=available_sources)
    model = cli_common.resolve_model(args)

    if args.ai_provider == "openai":
        _run_openai_chat(tools, dispatch, system_prompt, model, args)
    else:
        _run_anthropic_chat(tools, dispatch, system_prompt, model, args)


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="log-analyzer", description="AI-powered multi-cloud log analyzer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="One-shot analysis of a log source")
    analyze_provider_sub = analyze_parser.add_subparsers(dest="provider", required=True)
    for mod in PROVIDER_MODULES.values():
        mod.build_analyze_parser(analyze_provider_sub)

    list_parser = subparsers.add_parser("list", help="Discovery helpers")
    list_provider_sub = list_parser.add_subparsers(dest="provider", required=True)
    aws_cli.build_list_parser(list_provider_sub)  # only AWS has discovery helpers so far

    chat_parser = subparsers.add_parser("chat", help="Interactive natural-language chat over your logs")
    chat_parser.add_argument(
        "--provider",
        choices=list(PROVIDER_MODULES),
        default=None,
        help="Restrict chat tools to a single cloud provider (default: all configured providers)",
    )
    aws_cli.add_aws_args(chat_parser)
    gcp_cli.add_gcp_args(chat_parser)
    azure_cli.add_azure_args(chat_parser)
    cli_common.add_model_effort_args(chat_parser)
    chat_parser.set_defaults(func=cmd_chat)

    return parser


def main(argv: list[str] | None = None) -> int:
    # The AI backend's output is UTF-8 and may include characters (arrows,
    # em-dashes, etc.) that Windows consoles can't render in their default codepage.
    # Re-encode stdout/stderr as UTF-8, replacing anything truly unprintable.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception as exc:  # noqa: BLE001 -- top-level CLI error surface
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
