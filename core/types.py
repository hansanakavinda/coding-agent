"""Core type definitions for the agent framework."""

from dataclasses import dataclass, field
from typing import Any, Callable

# Callback type signature: confirm(action_name: str, preview_or_diff: str) -> bool
ConfirmationCallback = Callable[[str, str], bool]

# Status callback type signature: update_status(message: str | None) -> None
StatusCallback = Callable[[str | None], None]


@dataclass
class ToolCall:
    """Represents a tool execution requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Represents the outcome of executing a tool."""

    success: bool
    output: str
    error: str | None = None

    def to_message_content(self) -> str:
        """Format the result as content for the tool message."""
        if self.success:
            return self.output
        return f"Error: {self.error}"


@dataclass
class ProviderResponse:
    """Standardized response from an LLM provider."""

    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    model_used: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        """Check if model requested any tool invocations."""
        return len(self.tool_calls) > 0


@dataclass
class AgentStep:
    """Records an action or event during an agentic iteration."""

    kind: str  # "thought" | "tool_call" | "tool_result" | "final_answer"
    payload: Any


@dataclass
class AgentResult:
    """Final output and trace of an agent execution session."""

    final_response: str
    messages: list[dict[str, Any]]
    iterations: int
    steps: list[AgentStep] = field(default_factory=list)
