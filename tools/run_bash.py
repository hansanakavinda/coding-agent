"""Tool to execute shell commands with timeout and confirmation in workspace root."""

import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from core.types import ConfirmationCallback, ToolResult
from tools.base import BaseTool

DEFAULT_TIMEOUT_SECONDS = 30.0


class RunBashTool(BaseTool):
    """Executes shell commands within the project root directory."""

    def __init__(self, default_timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.default_timeout = default_timeout

    @property
    def name(self) -> str:
        return "run_bash"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command within the project root directory with a timeout. "
            "Use for running tests, build scripts, or terminal inspection."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The exact shell command line to run.",
                },
                "timeout": {
                    "type": "number",
                    "description": f"Maximum execution time in seconds (default {DEFAULT_TIMEOUT_SECONDS}s).",
                    "default": DEFAULT_TIMEOUT_SECONDS,
                },
            },
            "required": ["command"],
        }

    def execute(
        self,
        project_root: Path,
        confirmation_callback: ConfirmationCallback | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        command = kwargs.get("command")
        if not command or not command.strip():
            return ToolResult(
                success=False,
                output="",
                error="Missing required argument 'command'.",
            )

        timeout = float(kwargs.get("timeout") or self.default_timeout)

        # Require explicit confirmation if callback is provided
        if confirmation_callback is not None:
            preview = f"Command: {command}\nWorking directory: {project_root}"
            approved = confirmation_callback("run_bash", preview)
            if not approved:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"User rejected execution of command: {command}",
                )

        # Determine appropriate shell command per platform
        if sys.platform == "win32":
            # On Windows, run in PowerShell for broad command compatibility
            shell_args = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                f"{command}; exit $LASTEXITCODE",
            ]
        else:
            shell_args = ["/bin/bash", "-c", command]

        try:
            process = subprocess.run(
                shell_args,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout} seconds: {command}",
            )
        except Exception as err:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to execute command: {err}",
            )

        stdout = process.stdout.strip()
        stderr = process.stderr.strip()

        combined_output = []
        if stdout:
            combined_output.append(f"[STDOUT]\n{stdout}")
        if stderr:
            combined_output.append(f"[STDERR]\n{stderr}")
        if not combined_output:
            combined_output.append("(command completed with no output)")

        output_str = f"Exit code: {process.returncode}\n" + "\n\n".join(combined_output)

        if process.returncode != 0:
            return ToolResult(
                success=False,
                output=output_str,
                error=f"Command exited with non-zero status {process.returncode}.",
            )

        return ToolResult(success=True, output=output_str)
