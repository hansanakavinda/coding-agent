"""Unit tests for the run_bash tool."""

from pathlib import Path
import pytest

from tools.run_bash import RunBashTool


def test_run_bash_success(tmp_path: Path) -> None:
    """Verifies executing a simple command and capturing output."""
    tool = RunBashTool()
    # python -c is cross-platform across Windows PowerShell and Unix Bash
    result = tool.execute(
        project_root=tmp_path,
        command='python -c "print(\'Agent Shell Works\')"',
    )

    assert result.success is True
    assert "Exit code: 0" in result.output
    assert "Agent Shell Works" in result.output


def test_run_bash_non_zero_exit_code(tmp_path: Path) -> None:
    """Verifies that non-zero exit codes are captured cleanly."""
    tool = RunBashTool()
    result = tool.execute(
        project_root=tmp_path,
        command='python -c "import sys; sys.exit(42)"',
    )

    assert result.success is False
    assert "exited with non-zero status 42" in (result.error or "")


def test_run_bash_user_rejection(tmp_path: Path) -> None:
    """Verifies that user rejection prevents command execution."""
    tool = RunBashTool()

    def reject(action: str, details: str) -> bool:
        return False

    result = tool.execute(
        project_root=tmp_path,
        confirmation_callback=reject,
        command="python -c \"print('should not run')\"",
    )

    assert result.success is False
    assert "User rejected execution" in (result.error or "")


def test_run_bash_timeout(tmp_path: Path) -> None:
    """Verifies that long-running commands timeout gracefully."""
    tool = RunBashTool()
    result = tool.execute(
        project_root=tmp_path,
        command='python -c "import time; time.sleep(5)"',
        timeout=0.5,
    )

    assert result.success is False
    assert "timed out after 0.5 seconds" in (result.error or "")
