"""Turn fetched log events into plain text suitable for an AI model prompt."""

from datetime import datetime, timezone


def _fmt_ts(ts) -> str:
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
    return str(ts)


def format_events(events: list[dict], max_chars: int = 400_000) -> str:
    """Render {timestamp, message} events as newline-delimited text, truncated
    to a character budget so a single noisy fetch can't blow the context window.
    """
    if not events:
        return "(no log events found in this window)"

    lines = [f"[{_fmt_ts(e['timestamp'])}] {e['message']}" for e in events]
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... [truncated, {len(lines)} total events, showing first ~{max_chars} chars]"
    return text
