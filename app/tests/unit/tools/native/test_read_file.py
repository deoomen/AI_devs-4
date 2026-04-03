from pathlib import Path
from src.tools.native.read_file import _execute


async def test_read_full_file(workspace: Path):
    (workspace / "notes" / "hello.txt").write_text("line1\nline2\nline3\n")

    result = await _execute({"path": "notes/hello.txt"})

    assert not result.is_error
    assert "[lines 1-3 of 3]" in result.output
    assert "line1" in result.output
    assert "line3" in result.output


async def test_read_with_offset(workspace: Path):
    (workspace / "notes" / "data.txt").write_text("a\nb\nc\nd\n")

    result = await _execute({"path": "notes/data.txt", "offset": 2})

    assert not result.is_error
    assert "[lines 3-4 of 4]" in result.output
    assert "c" in result.output
    assert "a" not in result.output


async def test_read_with_limit(workspace: Path):
    (workspace / "notes" / "data.txt").write_text("a\nb\nc\nd\n")

    result = await _execute({"path": "notes/data.txt", "limit": 2})

    assert not result.is_error
    assert "[lines 1-2 of 4]" in result.output
    assert "a" in result.output
    assert "c" not in result.output


async def test_read_with_offset_and_limit(workspace: Path):
    (workspace / "notes" / "data.txt").write_text("a\nb\nc\nd\ne\n")

    result = await _execute({"path": "notes/data.txt", "offset": 1, "limit": 2})

    assert not result.is_error
    assert "[lines 2-3 of 5]" in result.output
    assert "b" in result.output
    assert "c" in result.output
    assert "a" not in result.output
    assert "d" not in result.output


async def test_read_missing_path():
    result = await _execute({})
    assert result.is_error
    assert "Missing path" in result.output


async def test_read_file_not_found(workspace: Path):  # pylint: disable=unused-argument
    result = await _execute({"path": "notes/nonexistent.txt"})
    assert result.is_error
    assert "File not found" in result.output


async def test_read_denied_path():
    result = await _execute({"path": "../escape.txt"})
    assert result.is_error
    assert "denied" in result.output


async def test_read_directory_not_a_file(workspace: Path):  # pylint: disable=unused-argument
    result = await _execute({"path": "notes"})
    assert result.is_error
    assert "Not a file" in result.output
