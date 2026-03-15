import json
import logging

import httpx

from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)

ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
DEFAULT_TIMEOUT = 30.0


async def _execute(arguments: dict) -> ToolResult:
    method = arguments.get("method", "GET").upper()
    url = arguments.get("url", "")
    headers = arguments.get("headers") or {}
    body = arguments.get("body")
    timeout = arguments.get("timeout", DEFAULT_TIMEOUT)

    if method not in ALLOWED_METHODS:
        return ToolResult(output=f"Invalid method: {method}", is_error=True)
    if not url:
        return ToolResult(output="Missing url", is_error=True)

    logger.debug("http_request %s %s", method, url)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            kwargs: dict = {"method": method, "url": url, "headers": headers}
            if body is not None and method in {"POST", "PUT", "PATCH"}:
                kwargs["json"] = body
            response = await client.request(**kwargs)
    except httpx.TimeoutException:
        return ToolResult(output=f"Request timed out after {timeout}s", is_error=True)
    except httpx.RequestError as e:
        return ToolResult(output=f"Request failed: {e}", is_error=True)

    # Try to parse as JSON, fall back to text
    try:
        result = response.json()
        body_str = json.dumps(result, ensure_ascii=False)
    except (json.JSONDecodeError, ValueError):
        body_str = response.text

    output = f"HTTP {response.status_code}\n{body_str}"
    logger.debug("http_request response: %d (%d bytes)", response.status_code, len(body_str))

    return ToolResult(output=output, is_error=response.status_code >= 400)


http_request_tool = Tool(
    name="http_request",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="http_request",
        description="Make an HTTP request to a URL and return the response.",
        parameters={
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                    "description": "HTTP method",
                },
                "url": {
                    "type": "string",
                    "description": "The URL to request",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP headers as key-value pairs",
                },
                "body": {
                    "type": "object",
                    "description": "Optional JSON request body (for POST/PUT/PATCH)",
                },
                "timeout": {
                    "type": "number",
                    "description": "Request timeout in seconds (default 30)",
                },
            },
            "required": ["method", "url"],
        },
    ),
    execute=_execute,
)
