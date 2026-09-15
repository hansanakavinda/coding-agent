"""Tool to write new files or overwrite files with user confirmation."""

from pathlib import Path
from typing import Any

from core.types import ConfirmationCallback, ToolResult
from tools.base import BaseTool, PathJailError, generate_diff, safe_resolve_path


class WriteFileTool(BaseTool):
    """Creates a new file or overwrites an existing file with confirmation."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "Create a new file or overwrite an existing file in the workspace with given content."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file to create or write.",
                },
                "content": {
                    "type": "string",
                    "description": "Full text content to write into the file.",
                },
            },
            "required": ["path", "content"],
        }

    def execute(
        self,
        project_root: Path,
        confirmation_callback: ConfirmationCallback | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        raw_path = kwargs.get("path")
        content = kwargs.get("content")

        if not raw_path or content is None:
            return ToolResult(
                success=False,
                output="",
                error="Missing required arguments: 'path' and 'content' must both be provided.",
            )

        try:
            target_path = safe_resolve_path(raw_path, project_root)
        except PathJailError as err:
            return ToolResult(success=False, output="", error=str(err))

        if target_path.exists() and target_path.is_dir():
            return ToolResult(
                success=False,
                output="",
                error=f"Cannot write to '{raw_path}': path exists and is a directory.",
            )

        # Prepare diff or preview for user confirmation
        if target_path.exists():
            try:
                old_text = target_path.read_text(encoding="utf-8")
                preview = generate_diff(old_text, content, raw_path)
            except Exception:
                preview = f"Overwriting existing file '{raw_path}' with {len(content.splitlines())} lines."
        else:
            lines = content.splitlines()
            preview_lines = lines[:15]
            preview_body = "\n".join(preview_lines)
            if len(lines) > 15:
                preview_body += f"\n... ({len(lines) - 15} more lines)"
            preview = f"Create new file '{raw_path}' ({len(lines)} lines):\n{preview_body}"

        # Require explicit confirmation if callback is attached
        if confirmation_callback is not None:
            approved = confirmation_callback("write_file", preview)
            if not approved:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"User rejected writing to '{raw_path}'.",
                )

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
        except Exception as err:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to write file '{raw_path}': {err}",
            )

        line_count = len(content.splitlines())
        return ToolResult(
            success=True,
            output=f"Successfully wrote {line_count} line(s) to '{raw_path}'.",
        )
