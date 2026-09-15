"""Unit tests for SessionManager and conversation resumption."""

from pathlib import Path

from memory.session import SessionManager


def test_session_creation_and_save(tmp_path: Path) -> None:
    """Verifies that sessions are saved as JSON files in .agent_sessions."""
    sm = SessionManager(tmp_path)
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

    assert filepath.exists()
    assert filepath.name == f"{session_id}.json"


def test_session_load(tmp_path: Path) -> None:
    """Verifies loading an existing session by ID."""
    sm = SessionManager(tmp_path)
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
    sm = SessionManager(tmp_path)

    sm.save_session("sess_a", "Task A", [], 1)
    sm.save_session("sess_b", "Task B", [], 2)

    sessions = sm.list_sessions()
    assert len(sessions) == 2
    ids = [s["session_id"] for s in sessions]
    assert "sess_a" in ids
    assert "sess_b" in ids
