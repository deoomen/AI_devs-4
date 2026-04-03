import pytest
from pathlib import Path
from src.tools.native.list_files import _execute


async def test_list_root_shows_standard_dirs(workspace: Path):
    result = await _execute({"path": "."})

    assert not result.is_error
    assert "d inbox" in result.output
    assert "d notes" in result.output
    assert "d outbox" in result.output


async def test_list_subdirectory(workspace: Path):
    (workspace / "notes" / "a.txt").write_text("x")
    (workspace / "notes" / "b.txt").write_text("y")
    (workspace / "notes" / "sub").mkdir()

    result = await _execute({"path": "notes"})

    assert not result.is_error
    assert "f a.txt" in result.output
    assert "f b.txt" in result.output
    assert "d sub" in result.output


async def test_list_empty_directory(workspace: Path):
    (workspace / "notes" / "empty").mkdir()

    result = await _execute({"path": "notes/empty"})

    assert not result.is_error
    assert result.output == "(empty)"


async def test_list_default_path_is_root(workspace: Path):
    result = await _execute({})

    assert not result.is_error
    assert "d notes" in result.output


async def test_list_directory_not_found(workspace: Path):
    result = await _execute({"path": "notes/nonexistent"})

    assert result.is_error
    assert "Directory not found" in result.output


async def test_list_not_a_directory(workspace: Path):
    (workspace / "notes" / "file.txt").write_text("data")

    result = await _execute({"path": "notes/file.txt"})

    assert result.is_error
    assert "Not a directory" in result.output


async def test_list_denied_path(workspace: Path):
    result = await _execute({"path": "../escape"})

    assert result.is_error
    assert "denied" in result.output
