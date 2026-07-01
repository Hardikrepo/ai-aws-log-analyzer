"""Shared configuration for the AI log analyzer."""

import os

from dotenv import load_dotenv

# Loads a .env file (if present, searching upward from the current working
# directory) into os.environ. Real environment variables always win --
# override=False means an OS-level ANTHROPIC_API_KEY takes precedence over
# whatever's in .env, so this is safe to add without disturbing an existing
# setup.
load_dotenv(override=False)

DEFAULT_MODEL = os.environ.get("LOG_ANALYZER_MODEL", "claude-opus-4-8")
OPENAI_DEFAULT_MODEL = os.environ.get("LOG_ANALYZER_OPENAI_MODEL", "gpt-5")
DEFAULT_MAX_TOKENS = 8192

# Hard cap on how many raw log lines/events get sent to the AI model in one request.
# Keeps a single analysis call from blowing past the context window on a noisy
# log group.
DEFAULT_MAX_EVENTS = 2000
