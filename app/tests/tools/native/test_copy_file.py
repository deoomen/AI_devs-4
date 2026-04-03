import pytest
from pathlib import Path
from src.tools.native.copy_file import _execute


async def test_copy_notes_to_outbox(workspace: Path):
    (workspace / "notes" / "source.txt").write_text("hello")

    result = await _execute({"src": "notes/source.txt", "dest": "outbox/dest.txt"})

    assert not result.is_error
    assert "notes/source.txt → outbox/dest.txt" in result.output
    assert (workspace / "outbox" / "dest.txt").read_text() == "hello"


async def test_copy_inbox_to_notes(workspace: Path):
    (workspace / "inbox" / "incoming.txt").write_text("data")

    result = await _execute({"src": "inbox/incoming.txt", "dest": "notes/copy.txt"})

    assert not result.is_error
    assert (workspace / "notes" / "copy.txt").read_text() == "data"


async def test_copy_creates_dest_subdirs(workspace: Path):
    (workspace / "notes" / "file.txt").write_text("content")

    result = await _execute({"src": "notes/file.txt", "dest": "outbox/sub/dir/file.txt"})

    assert not result.is_error
    assert (workspace / "outbox" / "sub" / "dir" / "file.txt").read_text() == "content"


async def test_copy_overwrites_existing_dest(workspace: Path):
    (workspace / "notes" / "src.txt").write_text("new content")
    (workspace / "outbox" / "dst.txt").write_text("old content")

    result = await _execute({"src": "notes/src.txt", "dest": "outbox/dst.txt"})

    assert not result.is_error
    assert (workspace / "outbox" / "dst.txt").read_text() == "new content"


async def test_copy_missing_src(workspace: Path):
    result = await _execute({"dest": "outbox/f.txt"})
    assert result.is_error
    assert "Missing src" in result.output


async def test_copy_missing_dest(workspace: Path):
    result = await _execute({"src": "notes/f.txt"})
    assert result.is_error
    assert "Missing dest" in result.output


async def test_copy_source_not_found(workspace: Path):
    result = await _execute({"src": "notes/missing.txt", "dest": "outbox/out.txt"})
    assert result.is_error
    assert "Source not found" in result.output


async def test_copy_source_is_directory(workspace: Path):
    result = await _execute({"src": "notes", "dest": "outbox/out.txt"})
    assert result.is_error
    assert "not a file" in result.output


async def test_copy_src_denied(workspace: Path):
    result = await _execute({"src": "../secret.txt", "dest": "outbox/out.txt"})
    assert result.is_error
    assert "denied" in result.output


async def test_copy_dest_denied_to_inbox(workspace: Path):
    (workspace / "notes" / "f.txt").write_text("x")
    result = await _execute({"src": "notes/f.txt", "dest": "inbox/f.txt"})
    assert result.is_error
    assert "denied" in result.output
