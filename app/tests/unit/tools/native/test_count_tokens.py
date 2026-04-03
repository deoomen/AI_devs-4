from pathlib import Path
from src.tools.native.count_tokens import _execute
from src.utils.tokens import CHARS_PER_TOKEN


async def test_count_tokens_from_text():
    text = "hello world"
    result = await _execute({"text": text})

    assert not result.is_error
    expected_tokens = int(len(text) / CHARS_PER_TOKEN)
    assert f"~{expected_tokens} tokens" in result.output
    assert f"{len(text)} chars" in result.output


async def test_count_tokens_reports_line_count():
    text = "line1\nline2\nline3"
    result = await _execute({"text": text})

    assert not result.is_error
    assert "3 lines" in result.output


async def test_count_tokens_trailing_newline_counts_correctly():
    # "a\nb\n" — ends with newline, so 2 lines (not 3)
    result = await _execute({"text": "a\nb\n"})
    assert not result.is_error
    assert "2 lines" in result.output


async def test_count_tokens_from_file(workspace: Path):
    content = "some file content here"
    (workspace / "notes" / "doc.txt").write_text(content)

    result = await _execute({"path": "notes/doc.txt"})

    assert not result.is_error
    assert f"{len(content)} chars" in result.output


async def test_count_tokens_missing_both():
    result = await _execute({})
    assert result.is_error
    assert "Provide either" in result.output


async def test_count_tokens_file_not_found(workspace: Path):  # pylint: disable=unused-argument
    result = await _execute({"path": "notes/missing.txt"})
    assert result.is_error
    assert "File not found" in result.output


async def test_count_tokens_denied_path():
    result = await _execute({"path": "../secret.txt"})
    assert result.is_error
    assert "denied" in result.output
