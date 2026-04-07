from loguru import logger

from src.domain.types import ToolType
from src.providers.openrouter import OpenRouterProvider
from ..types import Tool, ToolDefinition, ToolResult
from ..workspace import FileOp, safe_resolve


async def _execute(arguments: dict) -> ToolResult:
    text = arguments.get("text", "")
    output_path = arguments.get("output_path", "")
    voice = arguments.get("voice", "alloy")
    model = arguments.get("model") or None

    if not text:
        return ToolResult(output="Missing text", is_error=True)
    if not output_path:
        return ToolResult(output="Missing output_path", is_error=True)

    safe_out = safe_resolve(output_path, FileOp.WRITE)
    if safe_out is None:
        return ToolResult(output=f"Write denied: {output_path} (use notes/ or outbox/)", is_error=True)

    try:
        provider = OpenRouterProvider()
        audio_bytes = await provider.tts(text, model=model, voice=voice)
    except RuntimeError as e:
        return ToolResult(output=str(e), is_error=True)

    safe_out.parent.mkdir(parents=True, exist_ok=True)
    safe_out.write_bytes(audio_bytes)

    logger.info("text_to_speech: saved {} bytes → {}", len(audio_bytes), output_path)
    return ToolResult(output=f"Audio saved to {output_path} ({len(audio_bytes)} bytes)")


text_to_speech_tool = Tool(
    name="text_to_speech",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="text_to_speech",
        description=(
            "Convert text to speech and save the audio to a workspace file. "
            "Returns the output path on success. "
            "Use notes/ for intermediate audio files (e.g. notes/turn1.mp3)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to convert to speech.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Workspace-relative path to save the audio file (e.g. notes/turn1.mp3).",
                },
                "voice": {
                    "type": "string",
                    "description": "Voice to use. Options: alloy, echo, fable, onyx, nova, shimmer. Default: alloy.",
                    "default": "alloy",
                },
                "model": {
                    "type": "string",
                    "description": "TTS model override. Defaults to configured openrouter_default_tts_model.",
                },
            },
            "required": ["text", "output_path"],
        },
    ),
    execute=_execute,
)
