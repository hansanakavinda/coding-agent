"""Base classes and security primitives for agent tools."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from core.types import ToolResult


class PathJailError(PermissionError):
    """Raised when an operation attempts to access files outside the project root."""


def safe_resolve_path(target_path: str | Path, project_root: Path) -> Path:
    """Resolve a path safely, ensuring it remains strictly inside project_root.

    Args:
        target_path: Relative or absolute path provided by user or model.
        project_root: The root directory boundary of the workspace.

    Returns:
        Resolved Path object guaranteed to reside within project_root.

    Raises:
        PathJailError: If target_path resolves outside of project_root.
    """
    resolved_root = project_root.resolve()
    target = Path(target_path)

    # If target is relative, anchor it to project_root
    if not target.is_absolute():
        resolved_target = (resolved_root / target).resolve()
    else:
        resolved_target = target.resolve()

    try:
        # Check containment within project root
        resolved_target.relative_to(resolved_root)
    except ValueError as exc:
        raise PathJailError(
            f"Access denied: Path '{target_path}' resolves outside project root: {resolved_root}"
        ) from exc

    return resolved_target


class BaseTool(ABC):
    """Abstract base class for all agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the tool used in schemas and invocation."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Clear description of what the tool does and when to use it."""

    @property
    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        """JSON Schema defining the tool parameters."""

    @abstractmethod
    def execute(self, project_root: Path, **kwargs: Any) -> ToolResult:
        """Execute the tool against the given project root."""

    def to_openai_schema(self) -> dict[str, Any]:
        """Format the tool as an OpenAI-compatible function definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
