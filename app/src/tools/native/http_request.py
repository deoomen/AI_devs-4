import asyncio
import json
from urllib.parse import urlparse

import httpx
from loguru import logger

from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult

ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3


async def _do_request(client: httpx.AsyncClient, kwargs: dict) -> httpx.Response:
    return await client.request(**kwargs)


def _parse_body(response: httpx.Response) -> tuple[str, dict | None]:
    """Return (body_str, parsed_dict_or_none)."""
    try:
        result = response.json()
        return json.dumps(result, ensure_ascii=False), result
    except (json.JSONDecodeError, ValueError):
        return response.text, None


def _retry_delay(response: httpx.Response, parsed: dict | None) -> int | None:
    """Extract retry delay in seconds from 429/503 responses. Returns None if not retryable."""
    if response.status_code == 429:
        # Try body fields first (retry_after, retry_in, wait)
        if parsed and isinstance(parsed, dict):
            for key in ("retry_after", "retry_in", "wait"):
                val = parsed.get(key)
                if val is not None:
                    return int(val) + 1
        # Fall back to Retry-After header
        header = response.headers.get("Retry-After")
        if header:
            return int(header) + 1
        return 5  # default backoff for 429

    if response.status_code == 503:
        return 3

    return None


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

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ToolResult(output=f"Invalid URL: {url}", is_error=True)

    logger.debug("http_request {} {}", method, url)

    req_kwargs: dict = {"method": method, "url": url, "headers": headers}
    if body is not None and method in {"POST", "PUT", "PATCH"}:
        req_kwargs["json"] = body

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await _do_request(client, req_kwargs)
            body_str, parsed = _parse_body(response)

            # Retry on 429 / 503
            for attempt in range(MAX_RETRIES):
                delay = _retry_delay(response, parsed)
                if delay is None:
                    break
                logger.info("http_request {} (attempt {}), waiting {}s before retry", response.status_code, attempt + 1, delay)
                await asyncio.sleep(delay)
                response = await _do_request(client, req_kwargs)
                body_str, parsed = _parse_body(response)

    except httpx.TimeoutException:
        return ToolResult(output=f"Request timed out after {timeout}s", is_error=True)
    except httpx.RequestError as e:
        return ToolResult(output=f"Request failed: {e}", is_error=True)

    output = f"HTTP {response.status_code}\n{body_str}"
    logger.debug("http_request response: {} ({} bytes)", response.status_code, len(body_str))

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
