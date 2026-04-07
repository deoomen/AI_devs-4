import base64
import json
from datetime import datetime

import httpx
from loguru import logger

from src.config import settings
from src.domain.types import ToolType
from .transcribe_audio import _execute as _transcribe_execute
from ..types import Tool, ToolDefinition, ToolResult
from ..workspace import FileOp, safe_resolve

DEFAULT_TIMEOUT = 30.0


async def _execute(arguments: dict) -> ToolResult:
    action = arguments.get("action", "")
    audio_path = arguments.get("audio_path", "")

    if action not in ("start", "speak"):
        return ToolResult(output="action must be 'start' or 'speak'", is_error=True)
    if action == "speak" and not audio_path:
        return ToolResult(output="audio_path is required when action is 'speak'", is_error=True)

    url = f"{settings.aidevs4_headquarters_system_url}/verify"

    if action == "start":
        payload = {
            "apikey": settings.aidevs4_headquarters_api_key,
            "task": "phonecall",
            "answer": {"action": "start"},
        }
        logger.info("phonecall: starting session")
    else:
        safe_in = safe_resolve(audio_path, FileOp.READ)
        if safe_in is None:
            return ToolResult(output=f"Read denied: {audio_path}", is_error=True)
        if not safe_in.exists() or not safe_in.is_file():
            return ToolResult(output=f"File not found: {audio_path}", is_error=True)

        audio_b64 = base64.b64encode(safe_in.read_bytes()).decode()
        payload = {
            "apikey": settings.aidevs4_headquarters_api_key,
            "task": "phonecall",
            "answer": {"audio": audio_b64},
        }
        logger.info("phonecall: sending audio ({} bytes)", safe_in.stat().st_size)

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

    # Operator replied with audio — decode, save for review, transcribe, return text only
    if isinstance(result, dict) and "audio" in result:
        try:
            audio_bytes = base64.b64decode(result["audio"])
        except Exception as e:  # pylint: disable=broad-exception-caught
            return ToolResult(output=f"Failed to decode response audio: {e}", is_error=True)

        ts = datetime.now().strftime("%H%M%S_%f")[:11]
        parent = "/".join(audio_path.split("/")[:-1]) if "/" in audio_path else "notes"
        response_path = f"{parent}/response_{ts}.wav"
        safe_out = safe_resolve(response_path, FileOp.WRITE)
        if safe_out is None:
            return ToolResult(output=f"Write denied: {response_path}", is_error=True)

        safe_out.parent.mkdir(parents=True, exist_ok=True)
        safe_out.write_bytes(audio_bytes)
        logger.info("phonecall: saved response audio → {}", response_path)

        transcript_result = await _transcribe_execute({"path": response_path})
        if transcript_result.is_error:
            return ToolResult(output=f"Audio saved to {response_path} but transcription failed: {transcript_result.output}", is_error=True)
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
            "First call with action='start' to open the session. "
            "Then call with action='speak' and audio_path pointing to a WAV file generated with text_to_speech. "
            "Always returns text: either the operator's spoken words (transcribed automatically) "
            "or a plain text/flag response. Audio files are saved to the workspace for review."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "speak"],
                    "description": "'start' opens the session. 'speak' sends your audio turn.",
                },
                "audio_path": {
                    "type": "string",
                    "description": "Workspace-relative path to the WAV file to send (required for action='speak').",
                },
            },
            "required": ["action"],
        },
    ),
    execute=_execute,
)
