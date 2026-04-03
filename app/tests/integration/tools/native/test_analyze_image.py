from pathlib import Path
from unittest.mock import AsyncMock, patch
from src.tools.native.analyze_image import _execute, _is_url, _image_to_data_uri
from src.providers.types import ProviderResponse


# --- pure function tests ---

class TestIsUrl:
    def test_https(self):
        assert _is_url("https://example.com/photo.jpg") is True

    def test_http(self):
        assert _is_url("http://example.com/photo.jpg") is True

    def test_relative_path(self):
        assert _is_url("notes/image.png") is False

    def test_empty(self):
        assert _is_url("") is False


class TestImageToDataUri:
    def test_returns_none_for_missing_file(self, workspace: Path):  # pylint: disable=unused-argument
        assert _image_to_data_uri("notes/missing.png") is None

    def test_returns_data_uri_for_png(self, workspace: Path):
        # Write a minimal 1x1 PNG (valid PNG header)
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        (workspace / "notes" / "pixel.png").write_bytes(png_bytes)
        uri = _image_to_data_uri("notes/pixel.png")
        assert uri is not None
        assert uri.startswith("data:image/png;base64,")

    def test_returns_none_for_denied_path(self, workspace: Path):  # pylint: disable=unused-argument
        assert _image_to_data_uri("../escape.png") is None


# --- execute tests ---

def _mock_provider(text: str):
    mock = AsyncMock(return_value=ProviderResponse(content=text))
    return patch("src.tools.native.analyze_image.OpenRouterProvider", return_value=AsyncMock(chat=mock))


async def test_missing_path():
    result = await _execute({"prompt": "describe"})
    assert result.is_error
    assert "Missing path" in result.output


async def test_url_image_calls_provider():
    with _mock_provider("A sunny beach.") as MockProvider:
        MockProvider.return_value.chat = AsyncMock(return_value=ProviderResponse(content="A sunny beach."))
        result = await _execute({
            "path": "https://example.com/photo.jpg",
            "prompt": "What do you see?",
        })
    assert not result.is_error
    assert "A sunny beach." in result.output


async def test_file_image_calls_provider(workspace: Path):
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50  # minimal fake PNG
    (workspace / "notes" / "img.png").write_bytes(png_bytes)

    with patch("src.tools.native.analyze_image.OpenRouterProvider") as MockProvider:
        MockProvider.return_value.chat = AsyncMock(return_value=ProviderResponse(content="A small image."))
        result = await _execute({"path": "notes/img.png", "prompt": "Describe."})

    assert not result.is_error
    assert "A small image." in result.output


async def test_file_not_found_returns_error(workspace: Path):  # pylint: disable=unused-argument
    result = await _execute({"path": "notes/missing.png", "prompt": "Describe."})
    assert result.is_error
    assert "Cannot read image" in result.output


async def test_provider_error_returns_error():
    with patch("src.tools.native.analyze_image.OpenRouterProvider") as MockProvider:
        MockProvider.return_value.chat = AsyncMock(side_effect=RuntimeError("API error"))
        result = await _execute({
            "path": "https://example.com/photo.jpg",
            "prompt": "Describe.",
        })
    assert result.is_error
    assert "Vision API error" in result.output
