"""Unit tests for path jailing security checks."""

from pathlib import Path
import pytest

from tools.base import PathJailError, safe_resolve_path


def test_safe_resolve_relative_path(tmp_path: Path) -> None:
    """Verifies that relative paths within the project root resolve correctly."""
    sub_file = tmp_path / "subdir" / "file.txt"
    sub_file.parent.mkdir(parents=True)
    sub_file.write_text("hello", encoding="utf-8")

    resolved = safe_resolve_path("subdir/file.txt", tmp_path)
    assert resolved == sub_file.resolve()


def test_safe_resolve_prevents_parent_traversal(tmp_path: Path) -> None:
    """Verifies that ../ directory traversal outside project root is rejected."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()

    with pytest.raises(PathJailError) as exc_info:
        safe_resolve_path("../outside.txt", project_root)

    assert "resolves outside project root" in str(exc_info.value)


def test_safe_resolve_prevents_absolute_path_outside(tmp_path: Path) -> None:
    """Verifies that an absolute path outside project root is rejected."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()

    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret", encoding="utf-8")

    with pytest.raises(PathJailError):
        safe_resolve_path(str(outside_file), project_root)
