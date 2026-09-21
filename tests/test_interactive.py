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


def test_slash_command_completer_all_suggestions() -> None:
    """Verifies typing '/' yields all available slash command suggestions with metadata."""
    from prompt_toolkit.document import Document
    from cli import SlashCommandCompleter

    completer = SlashCommandCompleter()
    doc = Document("/")
    completions = list(completer.get_completions(doc, None))

    cmd_names = [c.text for c in completions]
    assert "/new-chat" in cmd_names
    assert "/history" in cmd_names
    assert "/model" in cmd_names
    assert "/clear" in cmd_names
    assert "/help" in cmd_names
    assert "/exit" in cmd_names
    assert len(completions) == 6


def test_slash_command_completer_prefix_filtering() -> None:
    """Verifies typing '/h' or '/n' narrows down the suggestions accordingly."""
    from prompt_toolkit.document import Document
    from cli import SlashCommandCompleter

    completer = SlashCommandCompleter()

    h_completions = list(completer.get_completions(Document("/h"), None))
    assert [c.text for c in h_completions] == ["/history", "/help"]

    n_completions = list(completer.get_completions(Document("/n"), None))
    assert [c.text for c in n_completions] == ["/new-chat"]


def test_slash_command_completer_ignores_non_slash_input() -> None:
    """Verifies that normal conversation queries do not trigger slash completions."""
    from prompt_toolkit.document import Document
    from cli import SlashCommandCompleter

    completer = SlashCommandCompleter()

    # Normal text
    assert list(completer.get_completions(Document("inspect files"), None)) == []

    # Slash command followed by arguments
    assert list(completer.get_completions(Document("/model extra"), None)) == []


def test_create_prompt_session_non_tty() -> None:
    """Verifies create_prompt_session returns None in non-interactive/non-TTY environments."""
    from cli import create_prompt_session
    import sys

    with patch.object(sys.stdin, "isatty", return_value=False):
        session = create_prompt_session()
        assert session is None


def test_make_confirmation_callback_auto_approve_returns_none() -> None:
    """Auto-approve mode disables confirmation callback."""
    from cli import make_confirmation_callback
    assert make_confirmation_callback(auto_approve=True) is None


def test_make_confirmation_callback_approve_option_1() -> None:
    """Option 1 approves tool execution."""
    from cli import make_confirmation_callback

    cb = make_confirmation_callback(auto_approve=False)
    assert cb is not None

    with patch("cli.prompt_action_confirmation", return_value=0):
        result = cb("run_bash", "$ pytest")
        assert result is True


def test_make_confirmation_callback_reject_option_2() -> None:
    """Option 2 rejects tool execution."""
    from cli import make_confirmation_callback

    cb = make_confirmation_callback(auto_approve=False)
    assert cb is not None

    with patch("cli.prompt_action_confirmation", return_value=1):
        result = cb("run_bash", "$ rm -rf /")
        assert result is False


def test_make_confirmation_callback_always_allow_option_3() -> None:
    """Option 3 enables auto-approve for remainder of session without prompting again."""
    from cli import make_confirmation_callback

    cb = make_confirmation_callback(auto_approve=False)
    assert cb is not None

    # First execution: user selects Option 3 (Always allow)
    with patch("cli.prompt_action_confirmation", return_value=2) as mock_prompt:
        result1 = cb("run_bash", "$ git status")
        assert result1 is True
        assert mock_prompt.call_count == 1

        # Second execution: should automatically return True without calling prompt
        result2 = cb("run_bash", "$ git diff")
        assert result2 is True
        assert mock_prompt.call_count == 1  # Unchanged!


def test_prompt_action_confirmation_non_tty() -> None:
    """Verifies fallback to Prompt.ask in non-TTY environments."""
    from cli import prompt_action_confirmation
    import sys

    options = ["1. Yes", "2. No", "3. Always"]
    with patch.object(sys.stdin, "isatty", return_value=False), \
         patch("rich.prompt.Prompt.ask", return_value="1"):
        assert prompt_action_confirmation("run_bash", options) == 0

    with patch.object(sys.stdin, "isatty", return_value=False), \
         patch("rich.prompt.Prompt.ask", return_value="2"):
        assert prompt_action_confirmation("run_bash", options) == 1

    with patch.object(sys.stdin, "isatty", return_value=False), \
         patch("rich.prompt.Prompt.ask", return_value="3"):
        assert prompt_action_confirmation("run_bash", options) == 2


def test_status_manager_lifecycle() -> None:
    """Verifies StatusManager starts, updates, and stops properly."""
    from rich.console import Console
    from cli import StatusManager

    console = Console(force_terminal=False)
    sm = StatusManager(console)
    assert not sm.is_active()

    # Start spinner
    sm.update("Thinking...")
    assert sm.is_active()

    # Update spinner message
    sm.update("Still Thinking...")
    assert sm.is_active()

    # Stop spinner with None
    sm.update(None)
    assert not sm.is_active()

    # Repeated stops are safe and idempotent
    sm.stop()
    assert not sm.is_active()


