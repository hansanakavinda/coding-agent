"""Core agentic loop implementation without external frameworks."""

import json
from pathlib import Path
from typing import Any, Callable

from core.types import AgentResult, AgentStep
from providers.base import LLMProvider
from tools import ToolRegistry, get_default_registry

DEFAULT_SYSTEM_PROMPT = """You are an autonomous AI coding assistant.
You have access to tools to inspect and interact with the local workspace.

Guidelines:
- Analyze requests carefully and use available tools to inspect code before making assumptions.
- Execute tools deliberately and observe their outputs to inform next steps.
- When your task is finished, return a comprehensive and direct summary in plain text without any tool calls.
"""


class AgentLoop:
    """Orchestrates the iterative model call -> tool dispatch -> result feedback loop."""

    def __init__(
        self,
        provider: LLMProvider,
        project_root: Path,
        tools: ToolRegistry | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_iterations: int = 15,
        on_step: Callable[[AgentStep], None] | None = None,
    ) -> None:
        self.provider = provider
        self.project_root = Path(project_root).resolve()
        self.tools = tools or get_default_registry()
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.on_step = on_step

    def run(self, task: str) -> AgentResult:
        """Execute the agent loop for a user-specified task."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]
        tool_schemas = self.tools.get_schemas()
        recorded_steps: list[AgentStep] = []

        for iteration in range(1, self.max_iterations + 1):
            response = self.provider.complete(messages=messages, tools=tool_schemas)

            # Record model thought / text if present
            if response.content:
                step = AgentStep(
                    kind="thought",
                    payload={"content": response.content, "model": response.model_used},
                )
                recorded_steps.append(step)
                if self.on_step:
                    self.on_step(step)

            # Check termination condition: no tool calls requested
            if not response.has_tool_calls:
                final_answer = response.content or ""
                final_step = AgentStep(
                    kind="final_answer",
                    payload={"content": final_answer, "model": response.model_used},
                )
                recorded_steps.append(final_step)
                if self.on_step:
                    self.on_step(final_step)

                return AgentResult(
                    final_response=final_answer,
                    messages=messages,
                    iterations=iteration,
                    steps=recorded_steps,
                )

            # Model requested tool calls: append assistant turn to message history
            assistant_turn: dict[str, Any] = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ],
            }
            messages.append(assistant_turn)

            # Dispatch each tool call and append tool output to history
            for tc in response.tool_calls:
                call_step = AgentStep(
                    kind="tool_call",
                    payload={"id": tc.id, "name": tc.name, "arguments": tc.arguments},
                )
                recorded_steps.append(call_step)
                if self.on_step:
                    self.on_step(call_step)

                result = self.tools.dispatch(
                    name=tc.name,
                    args=tc.arguments,
                    project_root=self.project_root,
                )

                result_step = AgentStep(
                    kind="tool_result",
                    payload={
                        "id": tc.id,
                        "name": tc.name,
                        "success": result.success,
                        "output": result.output,
                        "error": result.error,
                    },
                )
                recorded_steps.append(result_step)
                if self.on_step:
                    self.on_step(result_step)

                tool_message = {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": result.to_message_content(),
                }
                messages.append(tool_message)

        # Max iterations reached without a clean text response
        max_reached_msg = (
            f"Agent reached maximum iterations ({self.max_iterations}) without finishing."
        )
        return AgentResult(
            final_response=max_reached_msg,
            messages=messages,
            iterations=self.max_iterations,
            steps=recorded_steps,
        )
