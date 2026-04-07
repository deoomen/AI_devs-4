import base64
import json
from datetime import datetime

import httpx
from loguru import logger

from src.config import settings
from src.domain.types import ToolType
from .text_to_speech import _execute as _tts_execute
from .transcribe_audio import _execute as _transcribe_execute
from ..types import Tool, ToolDefinition, ToolResult
from ..workspace import FileOp, safe_resolve

DEFAULT_TIMEOUT = 30.0


async def _execute(arguments: dict) -> ToolResult:
    action = arguments.get("action", "")
    text = arguments.get("text", "")
    session_dir = arguments.get("session_dir", "").rstrip("/")

    if action not in ("start", "speak"):
        return ToolResult(output="action must be 'start' or 'speak'", is_error=True)
    if action == "speak" and not text:
        return ToolResult(output="text is required when action is 'speak'", is_error=True)
    if action == "speak" and not session_dir:
        return ToolResult(output="session_dir is required when action is 'speak' (use the value returned by action='start')", is_error=True)

    url = f"{settings.aidevs4_headquarters_system_url}/verify"

    if action == "start":
        ts = datetime.now().strftime("%H%M%S")
        session_dir = f"notes/session_{ts}"
        safe_dir = safe_resolve(session_dir, FileOp.WRITE)
        if safe_dir is None:
            return ToolResult(output=f"Write denied: {session_dir}", is_error=True)
        safe_dir.mkdir(parents=True, exist_ok=True)
        logger.info("phonecall: session dir → {}", safe_dir)

        payload = {
            "apikey": settings.aidevs4_headquarters_api_key,
            "task": "phonecall",
            "answer": {"action": "start"},
        }
        logger.info("phonecall: starting session")
    else:
        # Convert text to audio internally
        ts = datetime.now().strftime("%H%M%S_%f")[:11]
        turn_path = f"{session_dir}/turn_{ts}.wav"
        tts_result = await _tts_execute({"text": text, "output_path": turn_path})
        if tts_result.is_error:
            return ToolResult(output=f"TTS failed: {tts_result.output}", is_error=True)

        safe_in = safe_resolve(turn_path, FileOp.READ)
        if safe_in is None or not safe_in.exists():
            return ToolResult(output=f"TTS output not found: {turn_path}", is_error=True)

        audio_b64 = base64.b64encode(safe_in.read_bytes()).decode()
        payload = {
            "apikey": settings.aidevs4_headquarters_api_key,
            "task": "phonecall",
            "answer": {"audio": audio_b64},
        }
        logger.info("phonecall: sending audio ({} bytes) for text: {!r}", safe_in.stat().st_size, text[:60])

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(url, json=payload)
    except httpx.TimeoutException:
        return ToolResult(output=f"Request timed out after {DEFAULT_TIMEOUT}s", is_error=True)
    except httpx.RequestError as e:
        return ToolResult(output=f"Request failed: {e}", is_error=True)

    try:
        result = response.json()
    except (json.JSONDecodeError, ValueError):
        return ToolResult(
            output=f"HTTP {response.status_code}: {response.text}",
            is_error=response.status_code >= 400,
        )

    if response.status_code >= 400:
        return ToolResult(
            output=f"HTTP {response.status_code}: {json.dumps(result, ensure_ascii=False)}",
            is_error=True,
        )

    if action == "start":
        text_response = json.dumps(result, ensure_ascii=False)
        return ToolResult(output=f"Session started. Use session_dir='{session_dir}' for all turns.\n{text_response}")

    # Operator replied with audio — decode, save for review, transcribe, return text only
    if isinstance(result, dict) and "audio" in result:
        try:
            audio_bytes = base64.b64decode(result["audio"])
        except Exception as e:  # pylint: disable=broad-exception-caught
            return ToolResult(output=f"Failed to decode response audio: {e}", is_error=True)

        ts = datetime.now().strftime("%H%M%S_%f")[:11]
        response_path = f"{session_dir}/response_{ts}.wav"
        safe_out = safe_resolve(response_path, FileOp.WRITE)
        if safe_out is None:
            return ToolResult(output=f"Write denied: {response_path}", is_error=True)

        safe_out.parent.mkdir(parents=True, exist_ok=True)
        safe_out.write_bytes(audio_bytes)
        logger.info("phonecall: saved response audio → {} ({})", response_path, safe_out)

        transcript_result = await _transcribe_execute({"path": response_path})
        if transcript_result.is_error:
            return ToolResult(
                output=f"Audio saved to {response_path} but transcription failed: {transcript_result.output}",
                is_error=True,
            )

        transcription = transcript_result.output
        logger.info("phonecall: transcription done ({} chars)", len(transcription))

        other = {k: v for k, v in result.items() if k != "audio"}
        suffix = f"\n{json.dumps(other, ensure_ascii=False)}" if other else ""
        return ToolResult(output=f"Operator: {transcription}{suffix}")

    # Text or flag response — return as-is
    return ToolResult(output=json.dumps(result, ensure_ascii=False))


phonecall_tool = Tool(
    name="phonecall",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="phonecall",
        description=(
            "Conduct a phone call with the HQ operator for the 'phonecall' mission. "
            "Call with action='start' to open the session — returns a session_dir to use for all subsequent turns. "
            "Then call with action='speak', passing the text to say (in Polish) and the session_dir from start. "
            "Audio is generated and sent automatically. "
            "Always returns text: the operator's words (transcribed) or a plain text/flag response. "
            "All audio files are saved in session_dir for review."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "speak"],
                    "description": "'start' opens the session. 'speak' sends a spoken turn.",
                },
                "text": {
                    "type": "string",
                    "description": "The Polish text to speak to the operator (required for action='speak').",
                },
                "session_dir": {
                    "type": "string",
                    "description": "Session directory returned by action='start'. Required for action='speak'.",
                },
            },
            "required": ["action"],
        },
    ),
    execute=_execute,
)
