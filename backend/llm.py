"""Claude client. Every call forces a tool schema so outputs are JSON that code can check.

Without ANTHROPIC_API_KEY, or on any API error, callers get None and fall back to replay
logic that runs through the same verifiers.
"""
from __future__ import annotations

import logging
import os

from common import env

log = logging.getLogger("carethropic.llm")

MODEL = env("MODEL", "claude-sonnet-4-5")
FAST_MODEL = env("FAST_MODEL", MODEL)

_client = None


def live() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY")) and env("REPLAY") != "1"


def _get():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()
    return _client


def call_tool(system: str, content, tool_name: str, description: str, schema: dict,
              model: str | None = None, max_tokens: int = 1500) -> dict | None:
    if not live():
        return None
    try:
        msg = _get().messages.create(
            model=model or MODEL,
            max_tokens=max_tokens,
            system=system,
            tools=[{"name": tool_name, "description": description, "input_schema": schema}],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": content}],
        )
        for block in msg.content:
            if getattr(block, "type", "") == "tool_use":
                return dict(block.input)
    except Exception as e:  # network, auth, rate limit
        log.warning("Claude call failed, using replay: %s", e)
    return None
