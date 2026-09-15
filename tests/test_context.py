"""Unit tests for token counting and context budget management."""

from memory.context import ContextManager
from memory.tokens import count_message_tokens, count_tokens


def test_count_tokens_accuracy() -> None:
    """Verifies that count_tokens returns positive counts for non-empty text."""
    text = "def calculate_average(nums: list[float]) -> float:\n    return sum(nums) / len(nums)\n"
    tokens = count_tokens(text)
    assert tokens > 0
    assert count_tokens("") == 0


def test_count_message_tokens() -> None:
    """Verifies counting tokens across multi-turn messages."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": '{"path": "a.txt"}'},
                }
            ],
        },
        {"role": "tool", "name": "read_file", "tool_call_id": "call_1", "content": "file contents"},
    ]
    total = count_message_tokens(messages)
    assert total > 20


def test_truncate_tool_output_under_limit() -> None:
    """Verifies that output under limits is returned unchanged."""
    cm = ContextManager(max_tool_lines=10, max_tool_tokens=50)
    short = "line 1\nline 2\nline 3\n"
    assert cm.truncate_tool_output(short) == short


def test_truncate_tool_output_over_limit() -> None:
    """Verifies that large tool output is truncated with head and tail preserved."""
    cm = ContextManager(max_tool_lines=20, max_tool_tokens=20)
    lines = [f"line {i}" for i in range(1, 101)]
    large_output = "\n".join(lines)

    truncated = cm.truncate_tool_output(large_output)
    assert "line 1" in truncated
    assert "line 100" in truncated
    assert "[TRUNCATED:" in truncated
    assert len(truncated.splitlines()) < 50


def test_prune_messages_preserves_system_and_recent() -> None:
    """Verifies that pruning drops old intermediate turns and preserves recent ones."""
    # Set a low budget to trigger pruning
    cm = ContextManager(max_context_tokens=100)

    messages = [
        {"role": "system", "content": "System prompt."},
        {"role": "user", "content": "Task 1"},
        {"role": "assistant", "content": "Answer 1" * 30},  # ~60 tokens
        {"role": "user", "content": "Task 2"},
        {"role": "assistant", "content": "Answer 2" * 30},  # ~60 tokens
        {"role": "user", "content": "Task 3"},
        {"role": "assistant", "content": "Recent answer."},
    ]

    pruned = cm.prune_messages(messages, budget=100, keep_last_messages=2)

    # Must preserve system prompt
    assert pruned[0]["role"] == "system"
    assert pruned[0]["content"] == "System prompt."

    # Must include notice of pruning
    assert any("earlier conversation turns pruned" in m.get("content", "") for m in pruned)

    # Must preserve recent turns
    assert pruned[-1]["content"] == "Recent answer."
    assert pruned[-2]["content"] == "Task 3"
