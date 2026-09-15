"""Deterministic unit tests for the core agentic loop."""

from pathlib import Path
from typing import Any

from core.loop import AgentLoop
from core.types import ProviderResponse, ToolCall
from providers.base import LLMProvider
from tools import ToolRegistry, ReadFileTool


class MockProvider(LLMProvider):
    """Mock provider with a predefined sequence of responses."""

    def __init__(self, responses: list[ProviderResponse]) -> None:
        self.responses = list(responses)
        self.call_count = 0

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ProviderResponse:
        response = self.responses[self.call_count]
        self.call_count += 1
        return response


def test_agent_loop_executes_tool_and_terminates(tmp_path: Path) -> None:
    """Verifies that the loop calls a tool, gets output, and finishes cleanly."""
    test_file = tmp_path / "app.py"
    test_file.write_text("print('hello')", encoding="utf-8")

    responses = [
        # Turn 1: Model calls read_file
        ProviderResponse(
            content="Let me check app.py",
            tool_calls=[
                ToolCall(
                    id="call-123",
                    name="read_file",
                    arguments={"path": "app.py"},
                )
            ],
            model_used="mock-model",
        ),
        # Turn 2: Model finishes with final summary
        ProviderResponse(
            content="The app.py file prints 'hello'.",
            tool_calls=[],
            model_used="mock-model",
        ),
    ]

    mock_provider = MockProvider(responses)
    registry = ToolRegistry()
    registry.register(ReadFileTool())

    loop = AgentLoop(
        provider=mock_provider,
        project_root=tmp_path,
        tools=registry,
        max_iterations=5,
    )

    result = loop.run("What does app.py do?")

    assert result.iterations == 2
    assert result.final_response == "The app.py file prints 'hello'."
    assert len(result.messages) == 4
    # Messages: system, user, assistant (with tool_calls), tool (with output)
    assert result.messages[0]["role"] == "system"
    assert result.messages[1]["role"] == "user"
    assert result.messages[2]["role"] == "assistant"
    assert result.messages[3]["role"] == "tool"
    assert "1 | print('hello')" in result.messages[3]["content"]
