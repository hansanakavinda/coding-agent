"""Parser and prompt generator for ReAct-style prompted tool calling fallback."""

import json
import re
import uuid
from typing import Any

from core.types import ToolCall

FENCED_BLOCK_PATTERN = re.compile(
    r"```(?:json)?\s*(.*?)\s*```",
    re.DOTALL,
)


def generate_prompted_tools_instruction(tools_schemas: list[dict[str, Any]]) -> str:
    """Generate system prompt instructions describing tools for prompted calling."""
    lines: list[str] = [
        "## Tool Calling Instructions",
        "You have access to the following workspace tools:",
        "",
    ]

    for item in tools_schemas:
        fn = item.get("function", {})
        name = fn.get("name", "unknown")
        desc = fn.get("description", "")
        params = fn.get("parameters", {}).get("properties", {})
        required = fn.get("parameters", {}).get("required", [])

        lines.append(f"- **{name}**: {desc}")
        if params:
            lines.append("  Parameters:")
            for p_name, p_info in params.items():
                req_str = " (required)" if p_name in required else " (optional)"
                p_type = p_info.get("type", "any")
                p_desc = p_info.get("description", "")
                lines.append(f"    - `{p_name}` ({p_type}{req_str}): {p_desc}")
        lines.append("")

    lines.extend(
        [
            "To invoke a tool, you MUST emit a fenced JSON block in this exact format:",
            "```json",
            "{",
            '  "tool": "tool_name",',
            '  "args": {',
            '    "param1": "value1"',
            "  }",
            "}",
            "```",
            "Only call one tool at a time. Do not wrap normal answers in json fences.",
            "When your task is complete and no more tools are needed, answer in plain text.",
        ]
    )
    return "\n".join(lines)


def parse_prompted_tool_calls(
    content: str,
) -> tuple[str, list[ToolCall], str | None]:
    """Parse text content looking for fenced JSON tool calls.

    Returns:
        tuple of (thought_text, list_of_tool_calls, parse_error_or_none)
    """
    if not content:
        return "", [], None

    match = FENCED_BLOCK_PATTERN.search(content)
    if match:
        raw_json = match.group(1).strip()
        thought = (content[: match.start()] + content[match.end() :]).strip()
        # If the block contains tool keywords or looks like JSON, treat as tool attempt
        if not (raw_json.startswith("{") or raw_json.startswith("[") or "tool" in raw_json):
            return content, [], None
    else:
        # Check if content starts and ends with a bare JSON object containing "tool"
        trimmed = content.strip()
        if trimmed.startswith("{") and trimmed.endswith("}") and '"tool"' in trimmed:
            raw_json = trimmed
            thought = ""
        else:
            return content, [], None

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as err:
        return thought, [], f"Malformed JSON in tool call block: {err}"

    calls: list[ToolCall] = []
    items = parsed if isinstance(parsed, list) else [parsed]

    for item in items:
        if not isinstance(item, dict):
            return thought, [], "Tool call payload must be a JSON object."

        tool_name = item.get("tool")
        if not tool_name or not isinstance(tool_name, str):
            return (
                thought,
                [],
                "Missing or invalid 'tool' key in JSON payload (must be tool name string).",
            )

        args = item.get("args")
        if args is None:
            args = {}
        elif not isinstance(args, dict):
            return (
                thought,
                [],
                "The 'args' field in tool call payload must be a JSON dictionary.",
            )

        call_id = f"call_{uuid.uuid4().hex[:8]}"
        calls.append(ToolCall(id=call_id, name=tool_name, arguments=args))

    return thought, calls, None
