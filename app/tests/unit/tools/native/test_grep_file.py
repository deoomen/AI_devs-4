from pathlib import Path
from src.tools.native.grep_file import _execute


async def test_grep_finds_matches(workspace: Path):
    f = workspace / "notes" / "sample.txt"
    f.write_text("hello world\nfoo bar\nhello again\n")

    result = await _execute({"path": "notes/sample.txt", "pattern": "hello"})

    assert not result.is_error
    assert "[2 matches in 3 lines]" in result.output
    assert "1: hello world" in result.output
    assert "3: hello again" in result.output


async def test_grep_no_matches(workspace: Path):
    f = workspace / "notes" / "sample.txt"
    f.write_text("foo\nbar\n")

    result = await _execute({"path": "notes/sample.txt", "pattern": "xyz"})

    assert not result.is_error
    assert "[0 matches in 2 lines]" in result.output
    assert "No matches found." in result.output


async def test_grep_case_insensitive(workspace: Path):
    f = workspace / "notes" / "sample.txt"
    f.write_text("Hello World\n")

    result = await _execute({"path": "notes/sample.txt", "pattern": "hello"})

    assert not result.is_error
    assert "1: Hello World" in result.output


async def test_grep_invalid_regex(workspace: Path):
    f = workspace / "notes" / "sample.txt"
    f.write_text("anything\n")

    result = await _execute({"path": "notes/sample.txt", "pattern": "["})

    assert result.is_error
    assert "Invalid regex" in result.output


async def test_grep_missing_path():
    result = await _execute({"pattern": "hello"})
    assert result.is_error
    assert "Missing path" in result.output


async def test_grep_missing_pattern(workspace: Path):
    (workspace / "notes" / "f.txt").write_text("data")
    result = await _execute({"path": "notes/f.txt"})
    assert result.is_error
    assert "Missing pattern" in result.output


async def test_grep_file_not_found(workspace: Path):  # pylint: disable=unused-argument
    result = await _execute({"path": "notes/nonexistent.txt", "pattern": "x"})
    assert result.is_error
    assert "File not found" in result.output


async def test_grep_denied_path():
    result = await _execute({"path": "../secret.txt", "pattern": "x"})
    assert result.is_error
    assert "denied" in result.output


async def test_grep_binary_file_known_extension(workspace: Path):
    (workspace / "notes" / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)

    result = await _execute({"path": "notes/image.png", "pattern": "anything"})

    assert result.is_error
    assert "Skipped binary file" in result.output


async def test_grep_binary_file_null_bytes(workspace: Path):
    (workspace / "notes" / "data.bin").write_bytes(b"some\x00binary\x00data")

    result = await _execute({"path": "notes/data.bin", "pattern": "anything"})

    assert result.is_error
    assert "Skipped binary file" in result.output
