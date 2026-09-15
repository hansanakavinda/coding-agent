"""Unit tests for the write_file tool."""

from pathlib import Path

from tools.write_file import WriteFileTool


def test_write_new_file_creates_file_and_parents(tmp_path: Path) -> None:
    """Verifies that write_file creates a new file and any missing parent directories."""
    tool = WriteFileTool()
    sub_path = "nested/deep/module.py"
    content = "print('created')\n"

    result = tool.execute(project_root=tmp_path, path=sub_path, content=content)

    assert result.success is True
    created = tmp_path / "nested" / "deep" / "module.py"
    assert created.exists()
    assert created.read_text(encoding="utf-8") == content


def test_write_file_overwrite_existing(tmp_path: Path) -> None:
    """Verifies that write_file overwrites existing files when approved."""
    existing = tmp_path / "data.txt"
    existing.write_text("old content", encoding="utf-8")

    tool = WriteFileTool()
    result = tool.execute(
        project_root=tmp_path,
        path="data.txt",
        content="brand new content",
    )

    assert result.success is True
    assert existing.read_text(encoding="utf-8") == "brand new content"


def test_write_file_user_rejection(tmp_path: Path) -> None:
    """Verifies that user rejection prevents file creation."""
    tool = WriteFileTool()

    def reject(action: str, details: str) -> bool:
        return False

    result = tool.execute(
        project_root=tmp_path,
        confirmation_callback=reject,
        path="blocked.txt",
        content="should not exist",
    )

    assert result.success is False
    assert "User rejected" in (result.error or "")
    assert not (tmp_path / "blocked.txt").exists()


def test_write_file_path_jail(tmp_path: Path) -> None:
    """Verifies that write_file cannot write outside project root."""
    tool = WriteFileTool()
    result = tool.execute(
        project_root=tmp_path,
        path="../evil.py",
        content="malicious",
    )

    assert result.success is False
    assert "Access denied" in (result.error or "")
