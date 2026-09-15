"""Unit tests for the read_file tool."""

from pathlib import Path

from tools.read_file import ReadFileTool


def test_read_file_with_line_numbers(tmp_path: Path) -> None:
    """Verifies that read_file returns line-numbered text."""
    sample = tmp_path / "sample.py"
    sample.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    tool = ReadFileTool()
    result = tool.execute(project_root=tmp_path, path="sample.py")

    assert result.success is True
    assert "   1 | def hello():" in result.output
    assert "   2 |     return 'world'" in result.output


def test_read_empty_file(tmp_path: Path) -> None:
    """Verifies that reading an empty file returns a friendly placeholder."""
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")

    tool = ReadFileTool()
    result = tool.execute(project_root=tmp_path, path="empty.txt")

    assert result.success is True
    assert result.output == "<empty file>"


def test_read_nonexistent_file(tmp_path: Path) -> None:
    """Verifies that reading a nonexistent file reports a clear error."""
    tool = ReadFileTool()
    result = tool.execute(project_root=tmp_path, path="missing.py")

    assert result.success is False
    assert "File not found" in (result.error or "")


def test_read_directory_fails(tmp_path: Path) -> None:
    """Verifies that attempting to read a directory fails gracefully."""
    sub = tmp_path / "mydir"
    sub.mkdir()

    tool = ReadFileTool()
    result = tool.execute(project_root=tmp_path, path="mydir")

    assert result.success is False
    assert "Target path is a directory" in (result.error or "")


def test_read_outside_project_jailed(tmp_path: Path) -> None:
    """Verifies that directory traversal is blocked by the path jail."""
    tool = ReadFileTool()
    result = tool.execute(project_root=tmp_path, path="../secret.txt")

    assert result.success is False
    assert "Access denied" in (result.error or "")
