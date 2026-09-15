"""Tool to search for text patterns across project files."""

from pathlib import Path
import re
from typing import Any

from core.types import ToolResult
from tools.base import BaseTool, PathJailError, safe_resolve_path

IGNORED_DIRS = {
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
}
MAX_MATCHES = 100


class GrepTool(BaseTool):
    """Searches for regex or text patterns within files or directories."""

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return (
            "Search for a pattern (regular expression or text) within files in the workspace. "
            "Returns matching lines with their file paths and line numbers."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regular expression or literal text to search for.",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file path to search within (defaults to '.').",
                    "default": ".",
                },
            },
            "required": ["pattern"],
        }

    def execute(
        self,
        project_root: Path,
        confirmation_callback: Any = None,
        **kwargs: Any,
    ) -> ToolResult:
        pattern = kwargs.get("pattern")
        if not pattern:
            return ToolResult(
                success=False,
                output="",
                error="Missing required argument 'pattern'.",
            )

        raw_path = kwargs.get("path") or "."

        try:
            target = safe_resolve_path(raw_path, project_root)
        except PathJailError as err:
            return ToolResult(success=False, output="", error=str(err))

        if not target.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"Search path does not exist: '{raw_path}'",
            )

        try:
            regex = re.compile(pattern)
        except re.error:
            # Fall back to escaped literal pattern if regex compilation fails
            regex = re.compile(re.escape(pattern))

        matches: list[str] = []

        if target.is_file():
            self._search_file(target, project_root, regex, matches)
        else:
            self._search_dir(target, project_root, regex, matches)

        if not matches:
            return ToolResult(
                success=True,
                output=f"No matches found for pattern '{pattern}' in '{raw_path}'.",
            )

        output_lines = [f"Found {len(matches)} match(es):"]
        output_lines.extend(matches)
        if len(matches) >= MAX_MATCHES:
            output_lines.append(f"... (results capped at {MAX_MATCHES} matches)")

        return ToolResult(success=True, output="\n".join(output_lines))

    def _search_dir(
        self,
        directory: Path,
        project_root: Path,
        regex: re.Pattern[str],
        matches: list[str],
    ) -> None:
        """Walk directory tree, skipping ignored directories."""
        for path in directory.rglob("*"):
            if len(matches) >= MAX_MATCHES:
                break
            if any(part in IGNORED_DIRS for part in path.parts):
                continue
            if path.is_file():
                self._search_file(path, project_root, regex, matches)

    def _search_file(
        self,
        file_path: Path,
        project_root: Path,
        regex: re.Pattern[str],
        matches: list[str],
    ) -> None:
        """Search a single file line by line."""
        try:
            rel_path = file_path.relative_to(project_root).as_posix()
        except ValueError:
            rel_path = file_path.name

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for idx, line in enumerate(f, start=1):
                    if len(matches) >= MAX_MATCHES:
                        break
                    if regex.search(line):
                        matches.append(f"{rel_path}:{idx}: {line.rstrip()}")
        except Exception:
            pass
