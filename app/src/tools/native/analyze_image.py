import base64
import mimetypes

from loguru import logger

from src.config import settings
from src.domain.types import ToolType
from src.providers.openrouter import OpenRouterProvider
from src.providers.types import ProviderMessage
from ..types import Tool, ToolDefinition, ToolResult
from ..workspace import FileOp, safe_resolve


def _image_to_data_uri(path_str: str) -> str | None:
    """Read an image file from workspace and return a base64 data URI."""
    safe = safe_resolve(path_str, FileOp.READ)
    if safe is None or not safe.exists() or not safe.is_file():
        return None
    mime, _ = mimetypes.guess_type(safe.name)
    if mime is None:
        mime = "image/png"
    data = base64.b64encode(safe.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


async def _execute(arguments: dict) -> ToolResult:
    path = arguments.get("path", "")
    prompt = arguments.get("prompt", "Describe this image in detail.")

    if not path:
        return ToolResult(output="Missing path", is_error=True)

    data_uri = _image_to_data_uri(path)
    if data_uri is None:
        return ToolResult(
            output=f"Cannot read image: {path} (not found or access denied — use inbox/, notes/, or outbox/)",
            is_error=True,
        )

    logger.info("analyze_image {} with prompt: {}", path, prompt[:100])

    provider = OpenRouterProvider()
    message = ProviderMessage(
        role="user",
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_uri}},
        ],
    )

    try:
        response = await provider.chat(
            model=settings.openrouter_vision_model,
            messages=[message],
        )
    except Exception as e:
        logger.error("Vision API call failed: {}", e)
        return ToolResult(output=f"Vision API error: {e}", is_error=True)

    content = response.content or ""
    logger.info("analyze_image done ({} chars)", len(content))
    return ToolResult(output=content)


analyze_image_tool = Tool(
    name="analyze_image",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="analyze_image",
        description=(
            "Analyze an image file using a vision model. "
            "Takes a file path (relative to workspace) and an optional prompt describing what to look for. "
            "Returns a textual description/analysis of the image. "
            "The image must first be downloaded to the workspace (e.g. via download_file)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Image file path relative to workspace (e.g. notes/board.png)",
                },
                "prompt": {
                    "type": "string",
                    "description": "What to analyze in the image. Be specific about what information you need.",
                },
            },
            "required": ["path", "prompt"],
        },
    ),
    execute=_execute,
)
