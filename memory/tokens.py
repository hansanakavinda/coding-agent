"""Token estimation utilities using tiktoken with fallback heuristics."""

from typing import Any

try:
    import tiktoken

    _ENCODER = tiktoken.get_encoding("cl100k_base")
except Exception:
    _ENCODER = None


def count_tokens(text: str) -> int:
    """Estimate the number of tokens in a string."""
    if not text:
        return 0

    if _ENCODER is not None:
        try:
            return len(_ENCODER.encode(text, disallowed_special=()))
        except Exception:
            pass

    # Heuristic fallback: ~4 characters per token in English / code
    return max(1, len(text) // 4)


def count_message_tokens(messages: list[dict[str, Any]]) -> int:
    """Estimate the total token count of a list of message dicts.

    Accounts for message envelope formatting overhead (~4 tokens per message).
    """
    total = 0
    for msg in messages:
        # Per-message envelope overhead
        total += 4

        role = msg.get("role", "")
        total += count_tokens(role)

        content = msg.get("content")
        if content:
            total += count_tokens(str(content))

        name = msg.get("name")
        if name:
            total += count_tokens(str(name))

        tool_calls = msg.get("tool_calls")
        if tool_calls and isinstance(tool_calls, list):
            for tc in tool_calls:
                total += 4
                fn = tc.get("function", {})
                total += count_tokens(fn.get("name", ""))
                total += count_tokens(fn.get("arguments", ""))

    return total + 2  # priming tokens
