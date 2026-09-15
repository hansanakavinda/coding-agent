"""Unit tests for the grep tool."""

from pathlib import Path

from tools.grep import GrepTool


def test_grep_finds_pattern_in_files(tmp_path: Path) -> None:
    """Verifies that grep finds matching lines with relative paths and line numbers."""
    f1 = tmp_path / "mod1.py"
    f1.write_text("def solve_problem():\n    pass\n", encoding="utf-8")

    f2 = tmp_path / "mod2.py"
    f2.write_text("solve_problem()\nprint('done')\n", encoding="utf-8")

    tool = GrepTool()
    result = tool.execute(project_root=tmp_path, pattern="solve_problem", path=".")

    assert result.success is True
    assert "Found 2 match(es)" in result.output
    assert "mod1.py:1: def solve_problem():" in result.output
    assert "mod2.py:1: solve_problem()" in result.output


def test_grep_regex_pattern(tmp_path: Path) -> None:
    """Verifies that regex patterns work properly."""
    f = tmp_path / "calc.py"
    f.write_text("val_10 = 10\nval_20 = 20\nother = 30\n", encoding="utf-8")

    tool = GrepTool()
    result = tool.execute(project_root=tmp_path, pattern=r"val_\d+", path="calc.py")

    assert result.success is True
    assert "Found 2 match(es)" in result.output
    assert "calc.py:1: val_10 = 10" in result.output
    assert "calc.py:2: val_20 = 20" in result.output


def test_grep_no_matches(tmp_path: Path) -> None:
    """Verifies that searching for a non-existent pattern reports no matches."""
    f = tmp_path / "test.py"
    f.write_text("hello = True\n", encoding="utf-8")

    tool = GrepTool()
    result = tool.execute(project_root=tmp_path, pattern="nonexistent_word", path=".")

    assert result.success is True
    assert "No matches found" in result.output


def test_grep_path_jail(tmp_path: Path) -> None:
    """Verifies that grep enforces the path jail."""
    tool = GrepTool()
    result = tool.execute(project_root=tmp_path, pattern="pattern", path="../")

    assert result.success is False
    assert "Access denied" in (result.error or "")
