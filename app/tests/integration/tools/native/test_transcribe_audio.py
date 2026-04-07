from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.providers.types import ProviderResponse
from src.tools.native.transcribe_audio import SUPPORTED_EXTENSIONS, _execute

_FAKE_AUDIO = b"\xff\xfb\x90\x00" + b"\x00" * 64  # fake MP3 header bytes


def _mock_provider(text: str):
    return patch("src.tools.native.transcribe_audio.OpenRouterProvider", return_value=AsyncMock(
        chat=AsyncMock(return_value=ProviderResponse(content=text))
    ))


# ── validation ────────────────────────────────────────────────────────────────

async def test_missing_path():
    result = await _execute({})
    assert result.is_error
    assert "Missing path" in result.output


async def test_denied_path(workspace: Path):  # pylint: disable=unused-argument
    result = await _execute({"path": "../escape.mp3"})
    assert result.is_error
    assert "denied" in result.output


async def test_file_not_found(workspace: Path):  # pylint: disable=unused-argument
    result = await _execute({"path": "notes/missing.mp3"})
    assert result.is_error
    assert "File not found" in result.output


async def test_unsupported_format(workspace: Path):
    (workspace / "notes" / "clip.xyz").write_bytes(_FAKE_AUDIO)
    result = await _execute({"path": "notes/clip.xyz"})
    assert result.is_error
    assert "Unsupported audio format" in result.output
    assert ".xyz" in result.output


async def test_supported_extensions_coverage():
    # Ensure common formats are listed
    for ext in (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"):
        assert ext in SUPPORTED_EXTENSIONS


# ── provider interaction ──────────────────────────────────────────────────────

async def test_transcribes_mp3(workspace: Path):
    (workspace / "notes" / "clip.mp3").write_bytes(_FAKE_AUDIO)

    with _mock_provider("Hello from audio."):
        result = await _execute({"path": "notes/clip.mp3"})

    assert not result.is_error
    assert "Hello from audio." in result.output


async def test_transcribes_wav(workspace: Path):
    (workspace / "notes" / "clip.wav").write_bytes(_FAKE_AUDIO)

    with _mock_provider("Wave transcription."):
        result = await _execute({"path": "notes/clip.wav"})

    assert not result.is_error
    assert "Wave transcription." in result.output


async def test_provider_receives_data_uri(workspace: Path):
    (workspace / "notes" / "clip.mp3").write_bytes(_FAKE_AUDIO)

    with patch("src.tools.native.transcribe_audio.OpenRouterProvider") as MockProvider:
        mock_chat = AsyncMock(return_value=ProviderResponse(content="ok"))
        MockProvider.return_value.chat = mock_chat

        await _execute({"path": "notes/clip.mp3"})

    _, kwargs = mock_chat.call_args
    messages = kwargs.get("messages") or mock_chat.call_args.args[0] if mock_chat.call_args.args else kwargs["messages"]
    content = messages[0].content
    audio_part = next(p for p in content if p.get("type") == "image_url")
    assert audio_part["image_url"]["url"].startswith("data:audio/")
    assert ";base64," in audio_part["image_url"]["url"]


async def test_provider_uses_audio_model(workspace: Path):
    (workspace / "notes" / "clip.mp3").write_bytes(_FAKE_AUDIO)

    with patch("src.tools.native.transcribe_audio.OpenRouterProvider") as MockProvider:
        mock_chat = AsyncMock(return_value=ProviderResponse(content="ok"))
        MockProvider.return_value.chat = mock_chat

        await _execute({"path": "notes/clip.mp3"})

    _, kwargs = mock_chat.call_args
    from src.config import settings
    assert kwargs.get("model") == settings.openrouter_default_audio_model


async def test_provider_error_returns_error(workspace: Path):
    (workspace / "notes" / "clip.mp3").write_bytes(_FAKE_AUDIO)

    with patch("src.tools.native.transcribe_audio.OpenRouterProvider") as MockProvider:
        MockProvider.return_value.chat = AsyncMock(side_effect=RuntimeError("API down"))
        result = await _execute({"path": "notes/clip.mp3"})

    assert result.is_error
    assert "Transcription error" in result.output
