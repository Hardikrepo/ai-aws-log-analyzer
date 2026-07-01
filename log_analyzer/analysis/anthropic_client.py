"""Thin wrapper around the Anthropic Messages API."""

import anthropic

from .. import config


def get_client() -> anthropic.Anthropic:
    # Anthropic() resolves credentials from ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN,
    # or an `ant auth login` profile -- no key needs to be hardcoded here.
    return anthropic.Anthropic()


def _supports_thinking_and_effort(model: str) -> bool:
    return "haiku" not in model


def analyze(
    system_prompt: str,
    user_content: str,
    model: str = config.DEFAULT_MODEL,
    max_tokens: int = config.DEFAULT_MAX_TOKENS,
    effort: str = "high",
) -> anthropic.types.Message:
    """Single-shot analysis call. Returns the full Message (caller extracts text)."""
    client = get_client()

    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
    }
    if _supports_thinking_and_effort(model):
        kwargs["thinking"] = {"type": "adaptive"}
        kwargs["output_config"] = {"effort": effort}

    return client.messages.create(**kwargs)


def extract_text(message: anthropic.types.Message) -> str:
    return "".join(block.text for block in message.content if block.type == "text")


def extract_usage(message: anthropic.types.Message) -> dict:
    return {
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
        "cache_read_input_tokens": message.usage.cache_read_input_tokens,
    }
