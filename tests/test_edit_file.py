"""Unit tests for the edit_file tool, verifying exact-match logic and safety."""

from pathlib import Path
import pytest

from tools.edit_file import EditFileTool


def test_edit_file_exact_match_success(tmp_path: Path) -> None:
    """Verifies that an exact unique substring is successfully replaced."""
    target = tmp_path / "hello.py"
    target.write_text("def greet():\n    return 'hello world'\n", encoding="utf-8")

    tool = EditFileTool()
    result = tool.execute(
        project_root=tmp_path,
        path="hello.py",
        old_str="'hello world'",
        new_str="'hello universe'",
    )

    assert result.success is True
    assert "Successfully edited 'hello.py'" in result.output
    assert "-    return 'hello world'" in result.output
    assert "+    return 'hello universe'" in result.output

    updated_content = target.read_text(encoding="utf-8")
    assert "return 'hello universe'" in updated_content


def test_edit_file_fails_loudly_when_not_found(tmp_path: Path) -> None:
    """Verifies that edit_file fails loudly if old_str is not in the file."""
    target = tmp_path / "calc.py"
    target.write_text("x = 10\ny = 20\n", encoding="utf-8")

    tool = EditFileTool()
    result = tool.execute(
        project_root=tmp_path,
        path="calc.py",
        old_str="z = 30",
        new_str="z = 40",
    )

    assert result.success is False
    assert "was not found" in (result.error or "")
    # Original file must remain untouched
    assert target.read_text(encoding="utf-8") == "x = 10\ny = 20\n"


def test_edit_file_fails_loudly_when_multiple_matches(tmp_path: Path) -> None:
    """Verifies that edit_file fails loudly if old_str matches more than once."""
    target = tmp_path / "dup.py"
    target.write_text("val = 1\nval = 1\n", encoding="utf-8")

    tool = EditFileTool()
    result = tool.execute(
        project_root=tmp_path,
        path="dup.py",
        old_str="val = 1",
        new_str="val = 2",
    )

    assert result.success is False
    assert "found 2 times" in (result.error or "")
    assert "must match exactly once" in (result.error or "")
    # Original file must remain untouched
    assert target.read_text(encoding="utf-8") == "val = 1\nval = 1\n"


def test_edit_file_user_rejection(tmp_path: Path) -> None:
    """Verifies that user rejection prevents file modification."""
    target = tmp_path / "script.py"
    initial_content = "flag = False\n"
    target.write_text(initial_content, encoding="utf-8")

    def reject_all(action: str, details: str) -> bool:
        return False

    tool = EditFileTool()
    result = tool.execute(
        project_root=tmp_path,
        confirmation_callback=reject_all,
        path="script.py",
        old_str="flag = False",
        new_str="flag = True",
    )

    assert result.success is False
    assert "User rejected edit" in (result.error or "")
    assert target.read_text(encoding="utf-8") == initial_content


def test_edit_file_path_jail(tmp_path: Path) -> None:
    """Verifies that edit_file respects the path jail."""
    tool = EditFileTool()
    result = tool.execute(
        project_root=tmp_path,
        path="../outside.py",
        old_str="a",
        new_str="b",
    )

    assert result.success is False
    assert "Access denied" in (result.error or "")
