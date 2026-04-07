import base64
import mimetypes

from loguru import logger

from src.config import settings
from src.domain.types import Role, ToolType
from src.providers.openrouter import OpenRouterProvider
from src.providers.types import ProviderMessage
from ..types import Tool, ToolDefinition, ToolResult
from ..workspace import FileOp, safe_resolve

SUPPORTED_EXTENSIONS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg", ".oga", ".flac"}


async def _execute(arguments: dict) -> ToolResult:
    path = arguments.get("path", "")
    if not path:
        return ToolResult(output="Missing path", is_error=True)

    safe = safe_resolve(path, FileOp.READ)
    if safe is None:
        return ToolResult(output=f"Read denied: {path}", is_error=True)
    if not safe.exists() or not safe.is_file():
        return ToolResult(output=f"File not found: {path}", is_error=True)

    if safe.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return ToolResult(
            output=f"Unsupported audio format: {safe.suffix}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
            is_error=True,
        )

    logger.info("transcribe_audio: {} ({} bytes)", path, safe.stat().st_size)

    try:
        audio_bytes = safe.read_bytes()
    except OSError as e:
        return ToolResult(output=f"Failed to read file: {e}", is_error=True)

    mime, _ = mimetypes.guess_type(safe.name)
    if mime is None:
        mime = "audio/mpeg"

    data_uri = f"data:{mime};base64,{base64.b64encode(audio_bytes).decode()}"

    provider = OpenRouterProvider()
    message = ProviderMessage(
        role=Role.USER,
        content=[
            {"type": "text", "text": "Transcribe this audio file. Return only the transcription text, nothing else."},
            {"type": "image_url", "image_url": {"url": data_uri}},
        ],
    )

    try:
        response = await provider.chat(messages=[message], model=settings.openrouter_default_audio_model)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("transcribe_audio API call failed: {}", e)
        return ToolResult(output=f"Transcription error: {e}", is_error=True)

    transcription = response.content or ""
    logger.info("transcribe_audio done ({} chars)", len(transcription))
    return ToolResult(output=transcription)


transcribe_audio_tool = Tool(
    name="transcribe_audio",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="transcribe_audio",
        description=(
            "Transcribe an audio file to text using a multimodal model. "
            "Accepts a workspace file path (relative to workspace). "
            f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Audio file path relative to workspace (e.g. shared/mission21/interesting/msg_0012.mp3)",
                },
            },
            "required": ["path"],
        },
    ),
    execute=_execute,
)
