"""Argument-parsing and analysis helpers shared across all cloud providers."""

import argparse

from . import config
from .analysis import anthropic_client, openai_client, prompts
from .formatting import format_events

MODE_PROMPTS = {
    "anomaly": prompts.ANOMALY_SYSTEM_PROMPT,
    "security": prompts.SECURITY_SYSTEM_PROMPT,
    "cost": prompts.COST_PERFORMANCE_SYSTEM_PROMPT,
    "all": prompts.ALL_MODES_SYSTEM_PROMPT,
}

CHAT_MAX_CHARS = 150_000  # keep tool_result payloads bounded during a chat session

AI_BACKENDS = {"openai": openai_client, "anthropic": anthropic_client}
DEFAULT_MODELS = {"anthropic": config.DEFAULT_MODEL, "openai": config.OPENAI_DEFAULT_MODEL}


def resolve_model(args) -> str:
    return args.model or DEFAULT_MODELS[args.ai_provider]


def run_analysis(source_label: str, events: list[dict], args) -> None:
    backend = AI_BACKENDS[args.ai_provider]
    model = resolve_model(args)

    print(f"Fetched {len(events)} events from {source_label}. Sending to {args.ai_provider} ({model})...\n")
    system_prompt = MODE_PROMPTS[args.mode].format(source=source_label)
    log_text = format_events(events)
    message = backend.analyze(
        system_prompt=system_prompt,
        user_content=log_text,
        model=model,
        effort=args.effort,
    )
    print(backend.extract_text(message))
    usage = backend.extract_usage(message)
    print(
        f"\n--- tokens: input={usage['input_tokens']} "
        f"output={usage['output_tokens']} "
        f"cache_read={usage['cache_read_input_tokens']} ---"
    )


def add_model_effort_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--ai-provider", choices=list(AI_BACKENDS), default="openai", help="Which AI backend to use"
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            f"Model ID for the selected --ai-provider (defaults: '{config.DEFAULT_MODEL}' for "
            f"anthropic, '{config.OPENAI_DEFAULT_MODEL}' for openai)"
        ),
    )
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])


def add_mode_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=list(MODE_PROMPTS), default="all")
