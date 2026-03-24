import base64
import mimetypes

from loguru import logger

from src.domain.types import Role, ToolType
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


def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


async def _execute(arguments: dict) -> ToolResult:
    path = arguments.get("path", "")
    prompt = arguments.get("prompt", "Describe this image in detail.")

    if not path:
        return ToolResult(output="Missing path", is_error=True)

    if _is_url(path):
        image_url = path
    else:
        data_uri = _image_to_data_uri(path)
        if data_uri is None:
            return ToolResult(
                output=f"Cannot read image: {path} (not found or access denied — use inbox/, notes/, or outbox/)",
                is_error=True,
            )
        image_url = data_uri

    logger.info("analyze_image {} with prompt: {}", path, prompt)

    provider = OpenRouterProvider()
    message = ProviderMessage(
        role=Role.USER,
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url}},
        ],
    )

    try:
        response = await provider.chat(
            messages=[message],
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
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
            "Analyze an image using a vision model. "
            "Takes an image URL (http/https) or a file path (relative to workspace). "
            "Returns a textual description/analysis of the image. "
            "Prefer passing a URL directly when available — no need to download first."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Image URL (e.g. https://example.com/photo.png) or file path relative to workspace (e.g. notes/board.png)",
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
