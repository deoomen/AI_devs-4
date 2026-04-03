import pytest
from pathlib import Path
from src.tools.native.write_file import _execute


async def test_write_creates_file(workspace: Path):
    result = await _execute({"path": "notes/out.txt", "content": "hello"})

    assert not result.is_error
    assert "Written 5 bytes" in result.output
    assert (workspace / "notes" / "out.txt").read_text() == "hello"


async def test_write_overwrites_existing(workspace: Path):
    (workspace / "notes" / "f.txt").write_text("old content")

    result = await _execute({"path": "notes/f.txt", "content": "new"})

    assert not result.is_error
    assert (workspace / "notes" / "f.txt").read_text() == "new"


async def test_write_append(workspace: Path):
    (workspace / "notes" / "f.txt").write_text("first\n")

    result = await _execute({"path": "notes/f.txt", "content": "second\n", "append": True})

    assert not result.is_error
    assert "Appended 7 bytes" in result.output
    assert (workspace / "notes" / "f.txt").read_text() == "first\nsecond\n"


async def test_write_creates_subdirs(workspace: Path):
    result = await _execute({"path": "notes/sub/dir/file.txt", "content": "data"})

    assert not result.is_error
    assert (workspace / "notes" / "sub" / "dir" / "file.txt").read_text() == "data"


async def test_write_missing_path(workspace: Path):
    result = await _execute({"content": "data"})
    assert result.is_error
    assert "Missing path" in result.output


async def test_write_denied_to_inbox(workspace: Path):
    result = await _execute({"path": "inbox/file.txt", "content": "data"})
    assert result.is_error
    assert "denied" in result.output


async def test_write_denied_path_traversal(workspace: Path):
    result = await _execute({"path": "../escape.txt", "content": "data"})
    assert result.is_error
    assert "denied" in result.output
