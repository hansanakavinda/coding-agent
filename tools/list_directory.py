"""Tool to list directory contents safely within the workspace."""

from pathlib import Path
from typing import Any

from core.types import ToolResult
from tools.base import BaseTool, PathJailError, safe_resolve_path


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable units."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


class ListDirectoryTool(BaseTool):
    """Lists files and folders within a workspace directory."""

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return (
            "List files and subdirectories in a given directory path within the project. "
            "Defaults to project root if path is omitted or '.'."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative directory path to list (e.g. '.' or 'core').",
                    "default": ".",
                }
            },
        }

    def execute(
        self,
        project_root: Path,
        confirmation_callback: Any = None,
        **kwargs: Any,
    ) -> ToolResult:
        raw_path = kwargs.get("path") or "."

        try:
            target_dir = safe_resolve_path(raw_path, project_root)
        except PathJailError as err:
            return ToolResult(success=False, output="", error=str(err))

        if not target_dir.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"Directory does not exist: '{raw_path}'",
            )

        if not target_dir.is_dir():
            return ToolResult(
                success=False,
                output="",
                error=f"Target path is a file, not a directory: '{raw_path}'. Use read_file instead.",
            )

        try:
            entries = list(target_dir.iterdir())
        except Exception as err:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to read directory '{raw_path}': {err}",
            )

        # Filter out git internals to keep context clean
        visible_entries = [e for e in entries if e.name != ".git"]

        # Sort: directories first (alphabetical), then files (alphabetical)
        dirs = sorted([e for e in visible_entries if e.is_dir()], key=lambda x: x.name.lower())
        files = sorted([e for e in visible_entries if not e.is_dir()], key=lambda x: x.name.lower())

        lines: list[str] = []
        for d in dirs:
            lines.append(f"[DIR]  {d.name}/")
        for f in files:
            try:
                size_str = format_size(f.stat().st_size)
            except Exception:
                size_str = "unknown"
            lines.append(f"[FILE] {f.name} ({size_str})")

        if not lines:
            return ToolResult(success=True, output=f"Directory '{raw_path}' is empty.")

        header = f"Contents of '{raw_path}':\n"
        return ToolResult(success=True, output=header + "\n".join(lines))
