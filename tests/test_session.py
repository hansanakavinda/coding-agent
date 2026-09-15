"""Unit tests for SessionManager and centralized session storage."""

from pathlib import Path

from memory.session import SessionManager


def test_session_never_stored_in_workspace(tmp_path: Path) -> None:
    """Verifies that no session files or directories are created inside the project root."""
    workspace = tmp_path / "my_project"
    workspace.mkdir()
    central_dir = tmp_path / "central_sessions"

    sm = SessionManager(project_root=workspace, base_sessions_dir=central_dir)
    session_id = sm.generate_session_id()

    messages = [
        {"role": "system", "content": "System."},
        {"role": "user", "content": "Do work."},
    ]

    filepath = sm.save_session(
        session_id=session_id,
        task="Do work.",
        messages=messages,
        iterations=1,
    )

    # Central storage received the file
    assert filepath.exists()
    assert central_dir in filepath.parents

    # Project workspace must have zero session files or folders
    assert not (workspace / ".agent_sessions").exists()
    assert list(workspace.iterdir()) == []


def test_session_load(tmp_path: Path) -> None:
    """Verifies loading an existing session by ID."""
    workspace = tmp_path / "project_a"
    workspace.mkdir()
    central_dir = tmp_path / "central_sessions"

    sm = SessionManager(project_root=workspace, base_sessions_dir=central_dir)
    session_id = "test_sess_001"

    messages = [
        {"role": "system", "content": "You are a coding agent."},
        {"role": "user", "content": "Inspect code."},
        {"role": "assistant", "content": "Inspecting..."},
    ]

    sm.save_session(
        session_id=session_id,
        task="Inspect code.",
        messages=messages,
        iterations=2,
    )

    loaded = sm.load_session(session_id)
    assert loaded is not None
    assert loaded.session_id == session_id
    assert loaded.task == "Inspect code."
    assert loaded.iterations == 2
    assert len(loaded.messages) == 3


def test_list_sessions(tmp_path: Path) -> None:
    """Verifies listing multiple sessions."""
    workspace = tmp_path / "project_b"
    workspace.mkdir()
    central_dir = tmp_path / "central_sessions"

    sm = SessionManager(project_root=workspace, base_sessions_dir=central_dir)

    sm.save_session("sess_a", "Task A", [], 1)
    sm.save_session("sess_b", "Task B", [], 2)

    sessions = sm.list_sessions()
    assert len(sessions) == 2
    ids = [s["session_id"] for s in sessions]
    assert "sess_a" in ids
    assert "sess_b" in ids
