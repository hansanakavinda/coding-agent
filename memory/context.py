"""Context management: tool output truncation and conversation pruning."""

from typing import Any

from memory.tokens import count_message_tokens, count_tokens

DEFAULT_MAX_CONTEXT_TOKENS = 12000
DEFAULT_MAX_TOOL_LINES = 300
DEFAULT_MAX_TOOL_TOKENS = 2500


class ContextManager:
    """Monitors context token budget, truncates large tool outputs, and prunes old turns."""

    def __init__(
        self,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        max_tool_lines: int = DEFAULT_MAX_TOOL_LINES,
        max_tool_tokens: int = DEFAULT_MAX_TOOL_TOKENS,
    ) -> None:
        self.max_context_tokens = max_context_tokens
        self.max_tool_lines = max_tool_lines
        self.max_tool_tokens = max_tool_tokens

    def truncate_tool_output(self, output: str) -> str:
        """Truncate excessive tool outputs to prevent context window saturation.

        Preserves both head (imports/declarations) and tail (returns/summary).
        """
        if not output:
            return output

        lines = output.splitlines()
        token_count = count_tokens(output)

        if len(lines) <= self.max_tool_lines and token_count <= self.max_tool_tokens:
            return output

        # Preserve top and bottom segments
        head_count = self.max_tool_lines // 2
        tail_count = self.max_tool_lines // 2

        if len(lines) <= head_count + tail_count:
            head_count = len(lines) // 3
            tail_count = len(lines) // 3

        head_lines = lines[:head_count]
        tail_lines = lines[-tail_count:] if tail_count > 0 else []
        omitted_lines = len(lines) - len(head_lines) - len(tail_lines)

        truncation_marker = (
            f"\n... [TRUNCATED: {omitted_lines} lines omitted to stay within context budget. "
            "Use line ranges or grep to inspect specific sections] ...\n"
        )

        truncated = "\n".join(head_lines) + truncation_marker + "\n".join(tail_lines)
        return truncated

    def prune_messages(
        self,
        messages: list[dict[str, Any]],
        budget: int | None = None,
        keep_last_messages: int = 4,
    ) -> list[dict[str, Any]]:
        """Prune older conversation turns if total tokens exceed the context budget.

        Preserves:
        - The system prompt (index 0)
        - The most recent conversational turns (last keep_last_messages)
        Ensures assistant tool_calls and tool results are dropped together in atomic pairs.
        """
        target_budget = budget or self.max_context_tokens
        current_tokens = count_message_tokens(messages)

        if current_tokens <= target_budget:
            return messages

        if len(messages) <= keep_last_messages + 1:
            # Cannot safely prune if we only have system prompt + recent messages
            return messages

        system_msg = messages[0]
        recent_msgs = messages[-keep_last_messages:]
        intermediate_msgs = messages[1:-keep_last_messages]

        # Group intermediate messages into atomic turns
        # A turn is either a standalone user message, or an assistant message with its tool responses
        turns: list[list[dict[str, Any]]] = []
        current_turn: list[dict[str, Any]] = []

        for msg in intermediate_msgs:
            role = msg.get("role")
            if role in ("user", "assistant") and current_turn:
                turns.append(current_turn)
                current_turn = [msg]
            else:
                current_turn.append(msg)

        if current_turn:
            turns.append(current_turn)

        # Drop oldest turns until we are within budget
        dropped_turns_count = 0
        while turns and count_message_tokens([system_msg] + [m for t in turns for m in t] + recent_msgs) > target_budget:
            turns.pop(0)
            dropped_turns_count += 1

        pruned_intermediate: list[dict[str, Any]] = [m for t in turns for m in t]

        notice_msg = {
            "role": "system",
            "content": (
                f"[Notice: {dropped_turns_count} earlier conversation turns pruned to "
                f"remain within token budget ({target_budget} tokens). Recent turns preserved.]"
            ),
        }

        return [system_msg, notice_msg] + pruned_intermediate + recent_msgs
