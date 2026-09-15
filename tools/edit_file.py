"""Tool for targeted string replacements in files with diff preview and confirmation."""

from pathlib import Path
from typing import Any

from core.types import ConfirmationCallback, ToolResult
from tools.base import BaseTool, PathJailError, generate_diff, safe_resolve_path


class EditFileTool(BaseTool):
    """Performs exact targeted string replacements within an existing file."""

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return (
            "Replace an exact substring within a file with new content. "
            "The target substring ('old_str') must occur exactly once in the file to avoid accidental edits."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file to edit.",
                },
                "old_str": {
                    "type": "string",
                    "description": "The exact string to be replaced (must match uniquely).",
                },
                "new_str": {
                    "type": "string",
                    "description": "The replacement string.",
                },
            },
            "required": ["path", "old_str", "new_str"],
        }

    def execute(
        self,
        project_root: Path,
        confirmation_callback: ConfirmationCallback | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        raw_path = kwargs.get("path")
        old_str = kwargs.get("old_str")
        new_str = kwargs.get("new_str")

        if not raw_path or old_str is None or new_str is None:
            return ToolResult(
                success=False,
                output="",
                error="Missing required arguments: 'path', 'old_str', and 'new_str' must all be provided.",
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
        except Exception as err:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to read '{raw_path}': {err}",
            )

        # Enforce exact single-match requirement
        count = content.count(old_str)
        if count == 0:
            return ToolResult(
                success=False,
                output="",
                error=(
                    f"Target 'old_str' was not found in '{raw_path}'. "
                    "Ensure exact matching including whitespace and indentation."
                ),
            )
        if count > 1:
            return ToolResult(
                success=False,
                output="",
                error=(
                    f"Target 'old_str' found {count} times in '{raw_path}'. "
                    "It must match exactly once. Include more surrounding lines in 'old_str' to disambiguate."
                ),
            )

        new_content = content.replace(old_str, new_str, 1)
        diff_text = generate_diff(content, new_content, raw_path)

        # Explicit user confirmation check if a callback is provided
        if confirmation_callback is not None:
            approved = confirmation_callback("edit_file", diff_text)
            if not approved:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"User rejected edit to '{raw_path}'.",
                )

        try:
            target_path.write_text(new_content, encoding="utf-8")
        except Exception as err:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to write changes to '{raw_path}': {err}",
            )

        return ToolResult(
            success=True,
            output=f"Successfully edited '{raw_path}'.\n{diff_text}",
        )
