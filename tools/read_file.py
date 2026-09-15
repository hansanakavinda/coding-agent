"""Tool to read file contents with line numbers."""

from pathlib import Path
from typing import Any

from core.types import ToolResult
from tools.base import BaseTool, PathJailError, safe_resolve_path


class ReadFileTool(BaseTool):
    """Reads a file within the project directory and returns line-numbered content."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read the contents of a file within the workspace. "
            "Returns lines prefixed with their 1-based line numbers."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The relative or absolute file path to read (must be inside project root).",
                }
            },
            "required": ["path"],
        }

    def execute(self, project_root: Path, **kwargs: Any) -> ToolResult:
        raw_path = kwargs.get("path")
        if not raw_path:
            return ToolResult(
                success=False,
                output="",
                error="Missing required argument 'path'.",
            )

        try:
            target_path = safe_resolve_path(raw_path, project_root)
        except PathJailError as err:
            return ToolResult(success=False, output="", error=str(err))

        if not target_path.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"File not found: '{raw_path}'",
            )

        if not target_path.is_file():
            return ToolResult(
                success=False,
                output="",
                error=f"Target path is a directory, not a file: '{raw_path}'",
            )

        try:
            content = target_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = target_path.read_text(encoding="latin-1")
            except Exception as read_err:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Failed to decode file '{raw_path}': {read_err}",
                )
        except Exception as read_err:
            return ToolResult(
                success=False,
                output="",
                error=f"Could not read file '{raw_path}': {read_err}",
            )

        lines = content.splitlines()
        if not lines:
            return ToolResult(success=True, output="<empty file>")

        formatted_lines = [
            f"{idx:>4} | {line}" for idx, line in enumerate(lines, start=1)
        ]
        return ToolResult(success=True, output="\n".join(formatted_lines))
