"""Thin wrapper around the OpenAI Chat Completions API."""

import openai

from .. import config

# Reasoning models (gpt-5 family, o-series) support `reasoning_effort`; others
# (gpt-4o, gpt-4.1, etc.) reject the parameter outright.
_REASONING_MODEL_PREFIXES = ("gpt-5", "o1", "o3", "o4")

# Our CLI's effort scale is low/medium/high/xhigh/max; OpenAI's reasoning_effort
# only goes up to "high", so xhigh/max clamp down to it.
_EFFORT_MAP = {"low": "low", "medium": "medium", "high": "high", "xhigh": "high", "max": "high"}


def get_client() -> openai.OpenAI:
    # OpenAI() resolves the API key from the OPENAI_API_KEY environment variable --
    # no key needs to be hardcoded here.
    return openai.OpenAI()


def supports_reasoning_effort(model: str) -> bool:
    return model.startswith(_REASONING_MODEL_PREFIXES)


def map_effort(effort: str) -> str:
    return _EFFORT_MAP[effort]


def analyze(
    system_prompt: str,
    user_content: str,
    model: str = config.OPENAI_DEFAULT_MODEL,
    max_tokens: int = config.DEFAULT_MAX_TOKENS,
    effort: str = "high",
):
    """Single-shot analysis call. Returns the full ChatCompletion (caller extracts text)."""
    client = get_client()

    kwargs = {
        "model": model,
        "max_completion_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }
    if supports_reasoning_effort(model):
        kwargs["reasoning_effort"] = map_effort(effort)

    return client.chat.completions.create(**kwargs)


def extract_text(response) -> str:
    return response.choices[0].message.content or ""


def extract_usage(response) -> dict:
    usage = response.usage
    details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) if details is not None else 0
    return {
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "cache_read_input_tokens": cached or 0,
    }
