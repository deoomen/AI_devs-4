import httpx
from loguru import logger

from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult
from ..workspace import FileOp, safe_resolve

DEFAULT_TIMEOUT = 60.0


async def _execute(arguments: dict) -> ToolResult:
    url = arguments.get("url", "")
    path = arguments.get("path", "")

    if not url:
        return ToolResult(output="Missing url", is_error=True)
    if not path:
        return ToolResult(output="Missing path", is_error=True)

    safe = safe_resolve(path, FileOp.WRITE)
    if safe is None:
        return ToolResult(output=f"Write denied: {path} (use notes/ or outbox/)", is_error=True)

    timeout = arguments.get("timeout", DEFAULT_TIMEOUT)

    logger.info("download_file {} → {}", url, path)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
    except httpx.TimeoutException:
        return ToolResult(output=f"Download timed out after {timeout}s", is_error=True)
    except httpx.RequestError as e:
        return ToolResult(output=f"Download failed: {e}", is_error=True)

    if response.status_code >= 400:
        return ToolResult(
            output=f"HTTP {response.status_code}: {response.text[:200]}",
            is_error=True,
        )

    safe.parent.mkdir(parents=True, exist_ok=True)
    safe.write_bytes(response.content)

    size = len(response.content)
    line_count = response.text.count("\n")

    summary = f"Saved to {path} ({size} bytes, ~{line_count} lines)"
    logger.info("download_file done: {}", summary)
    return ToolResult(output=summary)


download_file_tool = Tool(
    name="download_file",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="download_file",
        description=(
            "Download a file from a URL and save it to the agent workspace. "
            "Returns only file metadata (path, size, line count) — not the content. "
            "Use read_file to inspect the content afterwards if needed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to download from",
                },
                "path": {
                    "type": "string",
                    "description": "Destination file path relative to workspace",
                },
                "timeout": {
                    "type": "number",
                    "description": "Download timeout in seconds (default 60)",
                },
            },
            "required": ["url", "path"],
        },
    ),
    execute=_execute,
)
