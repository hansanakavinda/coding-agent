"""Unit tests for the ReAct prompted fallback parser."""

from core.fallback_parser import generate_prompted_tools_instruction, parse_prompted_tool_calls


def test_parse_fenced_json_tool_call() -> None:
    """Verifies that fenced ```json block with tool and args is parsed cleanly."""
    content = """
I need to inspect the file first.
```json
{
  "tool": "read_file",
  "args": {
    "path": "main.py"
  }
}
```
Let me see what is inside.
"""
    thought, calls, error = parse_prompted_tool_calls(content)

    assert error is None
    assert len(calls) == 1
    assert calls[0].name == "read_file"
    assert calls[0].arguments == {"path": "main.py"}
    assert "I need to inspect the file first." in thought
    assert "Let me see what is inside." in thought


def test_parse_bare_json_tool_call() -> None:
    """Verifies that bare JSON without code fences is parsed."""
    content = '{"tool": "list_directory", "args": {"path": "."}}'
    thought, calls, error = parse_prompted_tool_calls(content)

    assert error is None
    assert len(calls) == 1
    assert calls[0].name == "list_directory"
    assert calls[0].arguments == {"path": "."}


def test_parse_malformed_json_returns_error() -> None:
    """Verifies that malformed JSON triggers an error string for retry prompting."""
    content = """
```json
{
  "tool": "read_file",
  "args": { "path": "broken.txt"
```
"""
    thought, calls, error = parse_prompted_tool_calls(content)

    assert len(calls) == 0
    assert error is not None
    assert "Malformed JSON in tool call block" in error


def test_parse_missing_tool_key_returns_error() -> None:
    """Verifies that JSON missing the 'tool' key returns an error."""
    content = """
```json
{
  "action": "read_file",
  "args": {"path": "test.txt"}
}
```
"""
    thought, calls, error = parse_prompted_tool_calls(content)

    assert len(calls) == 0
    assert error is not None
    assert "Missing or invalid 'tool' key" in error


def test_generate_prompted_tools_instruction() -> None:
    """Verifies generating system prompt instructions from schemas."""
    schemas = [
        {
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": "Edits a file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Target file"},
                    },
                    "required": ["path"],
                },
            },
        }
    ]

    instruction = generate_prompted_tools_instruction(schemas)
    assert "## Tool Calling Instructions" in instruction
    assert "**edit_file**" in instruction
    assert "`path` (string (required))" in instruction
    assert '```json' in instruction
