"""Unit tests for the list_directory tool."""

from pathlib import Path

from tools.list_directory import ListDirectoryTool


def test_list_directory_success(tmp_path: Path) -> None:
    """Verifies that list_directory shows folders and files with tags."""
    (tmp_path / "subfolder").mkdir()
    (tmp_path / "file1.py").write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "file2.txt").write_text("hello", encoding="utf-8")

    tool = ListDirectoryTool()
    result = tool.execute(project_root=tmp_path, path=".")

    assert result.success is True
    assert "[DIR]  subfolder/" in result.output
    assert "[FILE] file1.py" in result.output
    assert "[FILE] file2.txt" in result.output


def test_list_directory_skips_git_internals(tmp_path: Path) -> None:
    """Verifies that the .git folder is excluded from listing."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "main.py").write_text("print('main')", encoding="utf-8")

    tool = ListDirectoryTool()
    result = tool.execute(project_root=tmp_path, path=".")

    assert result.success is True
    assert ".git" not in result.output
    assert "main.py" in result.output


def test_list_directory_nonexistent(tmp_path: Path) -> None:
    """Verifies that a nonexistent directory path fails cleanly."""
    tool = ListDirectoryTool()
    result = tool.execute(project_root=tmp_path, path="does_not_exist")

    assert result.success is False
    assert "does not exist" in (result.error or "")


def test_list_directory_on_file_fails(tmp_path: Path) -> None:
    """Verifies that calling list_directory on a file fails with helpful guidance."""
    f = tmp_path / "a_file.txt"
    f.write_text("content", encoding="utf-8")

    tool = ListDirectoryTool()
    result = tool.execute(project_root=tmp_path, path="a_file.txt")

    assert result.success is False
    assert "is a file, not a directory" in (result.error or "")


def test_list_directory_path_jail(tmp_path: Path) -> None:
    """Verifies that list_directory prevents traversing outside project root."""
    tool = ListDirectoryTool()
    result = tool.execute(project_root=tmp_path, path="../")

    assert result.success is False
    assert "Access denied" in (result.error or "")
