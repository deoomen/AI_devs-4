from pathlib import Path
import httpx
import respx
from src.tools.native.download_file import _execute


@respx.mock
async def test_download_saves_file(workspace: Path):
    content = b"file content here\nline two\n"
    respx.get("https://files.example.com/data.txt").mock(
        return_value=httpx.Response(200, content=content)
    )
    result = await _execute({"url": "https://files.example.com/data.txt", "path": "notes/data.txt"})
    assert not result.is_error
    assert "notes/data.txt" in result.output
    assert f"{len(content)} bytes" in result.output
    assert (workspace / "notes" / "data.txt").read_bytes() == content


@respx.mock
async def test_download_creates_subdirs(workspace: Path):
    respx.get("https://files.example.com/f.txt").mock(
        return_value=httpx.Response(200, content=b"data")
    )
    result = await _execute({"url": "https://files.example.com/f.txt", "path": "notes/sub/dir/f.txt"})
    assert not result.is_error
    assert (workspace / "notes" / "sub" / "dir" / "f.txt").exists()


async def test_download_missing_url(workspace: Path):  # pylint: disable=unused-argument
    result = await _execute({"path": "notes/f.txt"})
    assert result.is_error
    assert "Missing url" in result.output


async def test_download_missing_path(workspace: Path):  # pylint: disable=unused-argument
    result = await _execute({"url": "https://files.example.com/f.txt"})
    assert result.is_error
    assert "Missing path" in result.output


async def test_download_denied_path(workspace: Path):  # pylint: disable=unused-argument
    result = await _execute({"url": "https://files.example.com/f.txt", "path": "inbox/f.txt"})
    assert result.is_error
    assert "denied" in result.output


@respx.mock
async def test_download_4xx_error(workspace: Path):  # pylint: disable=unused-argument
    respx.get("https://files.example.com/missing.txt").mock(
        return_value=httpx.Response(404, text="Not Found")
    )
    result = await _execute({"url": "https://files.example.com/missing.txt", "path": "notes/f.txt"})
    assert result.is_error
    assert "HTTP 404" in result.output


@respx.mock
async def test_download_timeout(workspace: Path):  # pylint: disable=unused-argument
    respx.get("https://files.example.com/slow.txt").mock(
        side_effect=httpx.TimeoutException("timed out")
    )
    result = await _execute({"url": "https://files.example.com/slow.txt", "path": "notes/f.txt"})
    assert result.is_error
    assert "timed out" in result.output


@respx.mock
async def test_download_request_error(workspace: Path):  # pylint: disable=unused-argument
    respx.get("https://files.example.com/down.txt").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    result = await _execute({"url": "https://files.example.com/down.txt", "path": "notes/f.txt"})
    assert result.is_error
    assert "Download failed" in result.output
