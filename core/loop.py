"""Core agentic loop implementation without external frameworks."""

import json
from pathlib import Path
from typing import Any, Callable

from core.fallback_parser import generate_prompted_tools_instruction, parse_prompted_tool_calls
from core.types import AgentResult, AgentStep, ConfirmationCallback, StatusCallback, ToolCall
from memory.context import ContextManager
from memory.session import SessionManager
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
        on_status: StatusCallback | None = None,
        confirmation_callback: ConfirmationCallback | None = None,
        enable_prompted_fallback: bool = True,
        context_manager: ContextManager | None = None,
        session_manager: SessionManager | None = None,
        session_id: str | None = None,
        initial_messages: list[dict[str, Any]] | None = None,
    ) -> None:
        self.provider = provider
        self.project_root = Path(project_root).resolve()
        self.tools = tools or get_default_registry()
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.on_step = on_step
        self.on_status = on_status
        self.confirmation_callback = confirmation_callback
        self.enable_prompted_fallback = enable_prompted_fallback
        self.context_manager = context_manager or ContextManager()
        self.session_manager = session_manager or SessionManager(self.project_root)
        self.session_id = session_id or self.session_manager.generate_session_id()
        self.initial_messages = initial_messages

    def run(self, task: str) -> AgentResult:
        """Execute the agent loop for a user-specified task."""
        tool_schemas = self.tools.get_schemas()

        full_system_prompt = self.system_prompt
        if self.enable_prompted_fallback:
            full_system_prompt += "\n\n" + generate_prompted_tools_instruction(tool_schemas)

        if self.initial_messages:
            messages: list[dict[str, Any]] = list(self.initial_messages)
            messages.append({"role": "user", "content": task})
        else:
            messages = [
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": task},
            ]

        recorded_steps: list[AgentStep] = []
        iteration = 1
        malformed_retry_count = 0

        # Save initial checkpoint
        self.session_manager.save_session(
            session_id=self.session_id,
            task=task,
            messages=messages,
            iterations=0,
        )

        while iteration <= self.max_iterations:
            # Prune message history if exceeding token budget
            messages = self.context_manager.prune_messages(messages)

            if self.on_status:
                self.on_status("Thinking...")
            try:
                response = self.provider.complete(messages=messages, tools=tool_schemas)
            finally:
                if self.on_status:
                    self.on_status(None)

            # Check if model emitted content
            content_text = response.content or ""

            # Check if content has malformed fenced tool calls needing retry
            thought, prompted_calls, parse_error = parse_prompted_tool_calls(content_text)
            if parse_error and malformed_retry_count < 1:
                malformed_retry_count += 1
                messages.append({"role": "assistant", "content": content_text})
                retry_prompt = (
                    f"Tool call parse error: {parse_error}\n"
                    "Please re-emit your tool call strictly inside a ```json code block with format:\n"
                    '```json\n{"tool": "tool_name", "args": {"param": "value"}}\n```\n'
                    "Or provide your final plain text answer."
                )
                messages.append({"role": "user", "content": retry_prompt})
                continue

            # Record model thought / text if present
            if content_text:
                step = AgentStep(
                    kind="thought",
                    payload={"content": content_text, "model": response.model_used},
                )
                recorded_steps.append(step)
                if self.on_step:
                    self.on_step(step)

            # Determine tool calls (native or prompted fallback)
            active_tool_calls: list[ToolCall] = response.tool_calls or prompted_calls

            # Check termination condition: no tool calls requested
            if not active_tool_calls:
                final_answer = content_text
                final_step = AgentStep(
                    kind="final_answer",
                    payload={"content": final_answer, "model": response.model_used},
                )
                recorded_steps.append(final_step)
                if self.on_step:
                    self.on_step(final_step)

                # Persist completed session state
                self.session_manager.save_session(
                    session_id=self.session_id,
                    task=task,
                    messages=messages,
                    iterations=iteration,
                )

                return AgentResult(
                    final_response=final_answer,
                    messages=messages,
                    iterations=iteration,
                    steps=recorded_steps,
                )

            # Model requested tool calls: append assistant turn to message history
            assistant_turn: dict[str, Any] = {
                "role": "assistant",
                "content": content_text,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in active_tool_calls
                ],
            }
            messages.append(assistant_turn)

            # Dispatch each tool call and append tool output to history
            for tc in active_tool_calls:
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
                    confirmation_callback=self.confirmation_callback,
                )

                # Truncate large tool output to protect context window
                raw_output = result.to_message_content()
                truncated_output = self.context_manager.truncate_tool_output(raw_output)

                result_step = AgentStep(
                    kind="tool_result",
                    payload={
                        "id": tc.id,
                        "name": tc.name,
                        "success": result.success,
                        "output": truncated_output,
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
                    "content": truncated_output,
                }
                messages.append(tool_message)

            # Persist checkpoint after each iteration turn
            self.session_manager.save_session(
                session_id=self.session_id,
                task=task,
                messages=messages,
                iterations=iteration,
            )

            iteration += 1

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
