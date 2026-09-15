"""Unit tests for interactive CLI slash commands and session history selection."""

from pathlib import Path
from unittest.mock import patch

from memory.session import SessionManager
from cli import (
    display_welcome_banner,
    display_slash_help,
    handle_model_switch,
    prompt_select_history,
    run_interactive_session,
)


def test_display_welcome_banner(tmp_path: Path) -> None:
    """Verifies welcome banner displays without errors."""
    display_welcome_banner(tmp_path, "openrouter/free", "sess_12345")


def test_display_slash_help() -> None:
    """Verifies slash commands help table displays cleanly."""
    display_slash_help()


def test_handle_model_switch_keeps_current_on_empty() -> None:
    """Keeps current model if user enters empty input."""
    with patch("rich.prompt.Prompt.ask", return_value=""):
        res = handle_model_switch("openrouter/free")
        assert res == "openrouter/free"


def test_handle_model_switch_updates_model() -> None:
    """Updates model when user inputs a valid model string."""
    with patch("rich.prompt.Prompt.ask", return_value="meta-llama/llama-3.3-70b:free"):
        res = handle_model_switch("openrouter/free")
        assert res == "meta-llama/llama-3.3-70b:free"


def test_prompt_select_history_empty_sessions(tmp_path: Path) -> None:
    """Returns None when no sessions exist for workspace."""
    workspace = tmp_path / "proj"
    workspace.mkdir()
    central = tmp_path / "central"

    sm = SessionManager(project_root=workspace, base_sessions_dir=central)
    result = prompt_select_history(sm)
    assert result is None


def test_prompt_select_history_numeric_selection(tmp_path: Path) -> None:
    """Allows selecting a session by its index number."""
    workspace = tmp_path / "proj"
    workspace.mkdir()
    central = tmp_path / "central"

    sm = SessionManager(project_root=workspace, base_sessions_dir=central)
    sm.save_session(
        session_id="sess_001",
        task="First Task",
        messages=[{"role": "user", "content": "Hello"}],
        iterations=1,
    )

    # User enters "1" to pick the first session
    with patch("rich.prompt.Prompt.ask", return_value="1"):
        res = prompt_select_history(sm)
        assert res is not None
        selected_id, selected_msgs = res
        assert selected_id == "sess_001"
        assert len(selected_msgs) == 1
        assert selected_msgs[0]["content"] == "Hello"


def test_prompt_select_history_cancellation(tmp_path: Path) -> None:
    """Returns None when user presses Enter to cancel."""
    workspace = tmp_path / "proj"
    workspace.mkdir()
    central = tmp_path / "central"

    sm = SessionManager(project_root=workspace, base_sessions_dir=central)
    sm.save_session("sess_001", "Task", [], 1)

    with patch("rich.prompt.Prompt.ask", return_value=""):
        res = prompt_select_history(sm)
        assert res is None


def test_interactive_session_slash_commands_flow(tmp_path: Path) -> None:
    """Simulates interactive session executing /help, /new-chat, and /exit."""
    workspace = tmp_path / "proj"
    workspace.mkdir()

    # User types /help, then /new-chat, then /exit
    inputs = ["/help", "/new-chat", "/exit"]

    with patch("cli.resolve_api_key", return_value="test-key"), \
         patch("rich.prompt.Prompt.ask", side_effect=inputs):
        run_interactive_session(
            workspace=workspace,
            auto_approve=True,
            initial_model="openrouter/free",
        )
