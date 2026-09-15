"""Tests verifying prompted tool calling and retry-on-malformed-output within AgentLoop."""

from pathlib import Path
from typing import Any

from core.loop import AgentLoop
from core.types import ProviderResponse
from providers.base import LLMProvider
from tools import ToolRegistry, ReadFileTool


class StepMockProvider(LLMProvider):
    """Returns predefined responses in order."""

    def __init__(self, responses: list[ProviderResponse]) -> None:
        self.responses = list(responses)
        self.call_history: list[list[dict[str, Any]]] = []

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ProviderResponse:
        self.call_history.append(messages)
        return self.responses.pop(0)


def test_agent_loop_prompted_fallback(tmp_path: Path) -> None:
    """Verifies that a model emitting fenced ```json blocks triggers tool execution."""
    sample = tmp_path / "info.txt"
    sample.write_text("Secret Token: 42", encoding="utf-8")

    responses = [
        # Turn 1: Model outputs fenced JSON block instead of native tool_calls
        ProviderResponse(
            content='Checking the file.\n```json\n{"tool": "read_file", "args": {"path": "info.txt"}}\n```',
            tool_calls=[],
            model_used="prompted-model",
        ),
        # Turn 2: Model finishes with plain text
        ProviderResponse(
            content="The secret token is 42.",
            tool_calls=[],
            model_used="prompted-model",
        ),
    ]

    provider = StepMockProvider(responses)
    registry = ToolRegistry()
    registry.register(ReadFileTool())

    loop = AgentLoop(
        provider=provider,
        project_root=tmp_path,
        tools=registry,
        max_iterations=5,
    )

    result = loop.run("What is the token?")

    assert result.final_response == "The secret token is 42."
    # Tool output was captured
    tool_msgs = [m for m in result.messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert "Secret Token: 42" in tool_msgs[0]["content"]


def test_agent_loop_retries_on_malformed_tool_call(tmp_path: Path) -> None:
    """Verifies that AgentLoop catches broken JSON and reprompts before giving up."""
    sample = tmp_path / "info.txt"
    sample.write_text("Hello from file", encoding="utf-8")

    responses = [
        # Turn 1: Model outputs malformed JSON
        ProviderResponse(
            content='Let me read: ```json\n{"tool": "read_file", "args": { broken...\n```',
            tool_calls=[],
            model_used="prompted-model",
        ),
        # Turn 2: After receiving parse error prompt, model fixes the JSON
        ProviderResponse(
            content='Apologies. Here is the corrected call:\n```json\n{"tool": "read_file", "args": {"path": "info.txt"}}\n```',
            tool_calls=[],
            model_used="prompted-model",
        ),
        # Turn 3: Final response
        ProviderResponse(
            content="File says hello.",
            tool_calls=[],
            model_used="prompted-model",
        ),
    ]

    provider = StepMockProvider(responses)
    registry = ToolRegistry()
    registry.register(ReadFileTool())

    loop = AgentLoop(
        provider=provider,
        project_root=tmp_path,
        tools=registry,
        max_iterations=5,
    )

    result = loop.run("Read info.txt")

    assert result.final_response == "File says hello."
    # Check that retry message was sent
    retry_user_msgs = [
        m for m in result.messages
        if m.get("role") == "user" and "Tool call parse error" in m.get("content", "")
    ]
    assert len(retry_user_msgs) == 1
