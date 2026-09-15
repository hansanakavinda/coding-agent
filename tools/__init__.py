"""Tools registry and dispatch management."""

from pathlib import Path
from typing import Any

from core.types import ConfirmationCallback, ToolResult
from tools.base import BaseTool, PathJailError, generate_diff, safe_resolve_path
from tools.edit_file import EditFileTool
from tools.grep import GrepTool
from tools.list_directory import ListDirectoryTool
from tools.read_file import ReadFileTool
from tools.run_bash import RunBashTool
from tools.write_file import WriteFileTool


class ToolRegistry:
    """Manages available tools, schema generation, and execution dispatch."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a new tool instance."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_schemas(self) -> list[dict[str, Any]]:
        """Return OpenAI-compatible tool definitions for all registered tools."""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def dispatch(
        self,
        name: str,
        args: dict[str, Any],
        project_root: Path,
        confirmation_callback: ConfirmationCallback | None = None,
    ) -> ToolResult:
        """Dispatch a tool call to the registered handler."""
        tool = self._tools.get(name)
        if not tool:
            available = ", ".join(self._tools.keys()) or "none"
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool '{name}'. Available tools: {available}",
            )

        try:
            return tool.execute(
                project_root=project_root,
                confirmation_callback=confirmation_callback,
                **args,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{name}' raised unexpected exception: {exc}",
            )


def get_default_registry() -> ToolRegistry:
    """Build and return the complete default tool registry."""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(ListDirectoryTool())
    registry.register(GrepTool())
    registry.register(EditFileTool())
    registry.register(WriteFileTool())
    registry.register(RunBashTool())
    return registry


__all__ = [
    "BaseTool",
    "EditFileTool",
    "GrepTool",
    "ListDirectoryTool",
    "PathJailError",
    "ReadFileTool",
    "RunBashTool",
    "ToolRegistry",
    "WriteFileTool",
    "generate_diff",
    "get_default_registry",
    "safe_resolve_path",
]
