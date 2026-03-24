import asyncio
import json

import httpx
from loguru import logger

from src.config import settings
from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult

ZMAIL_URL = f"{settings.aidevs4_headquarters_system_url}/api/zmail"
DEFAULT_TIMEOUT = 30.0


async def _execute(arguments: dict) -> ToolResult:
    action = arguments.get("action", "")
    params = arguments.get("params") or {}

    if not action:
        return ToolResult(output="Missing action", is_error=True)

    payload = {
        "apikey": settings.aidevs4_headquarters_api_key,
        "action": action,
        **params,
    }

    logger.info("zmail action={} params={}", action, {k: v for k, v in params.items()})

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(ZMAIL_URL, json=payload)
    except httpx.TimeoutException:
        return ToolResult(output=f"Request timed out after {DEFAULT_TIMEOUT}s", is_error=True)
    except httpx.RequestError as e:
        return ToolResult(output=f"Request failed: {e}", is_error=True)

    try:
        result = response.json()
        body_str = json.dumps(result, ensure_ascii=False)
    except (json.JSONDecodeError, ValueError):
        result = {}
        body_str = response.text

    logger.info("zmail response: {} {}", response.status_code, body_str)

    # Respect retry_after on 429
    if response.status_code == 429 and isinstance(result, dict):
        retry_after = result.get("retry_after")
        if retry_after:
            wait = int(retry_after) + 1
            logger.info("zmail rate limited, waiting {}s", wait)
            await asyncio.sleep(wait)
            try:
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                    response = await client.post(ZMAIL_URL, json=payload)
                try:
                    result = response.json()
                    body_str = json.dumps(result, ensure_ascii=False)
                except (json.JSONDecodeError, ValueError):
                    body_str = response.text
                logger.info("zmail retry response: {} {}", response.status_code, body_str)
            except (httpx.TimeoutException, httpx.RequestError) as e:
                return ToolResult(output=f"Retry failed: {e}", is_error=True)

    output = f"HTTP {response.status_code}\n{body_str}"
    return ToolResult(output=output, is_error=response.status_code >= 400)


zmail_tool = Tool(
    name="zmail",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="zmail",
        description=(
            "Interact with the zmail email API to search and read emails. "
            "API key is injected automatically. "
            "Start with action 'help' to discover available actions and their parameters. "
            "Common actions: 'help' (list actions), 'getInbox' (list emails, paginated). "
            "The API supports Gmail-style search operators: from:, to:, subject:, OR, AND."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "API action to perform (start with 'help' to discover available actions)",
                },
                "params": {
                    "type": "object",
                    "description": (
                        "Additional parameters for the action as key-value pairs. "
                        "Discover available parameters via the 'help' action. "
                        "Example: {\"page\": 1} or {\"query\": \"from:someone@example.com\"}"
                    ),
                },
            },
            "required": ["action"],
        },
    ),
    execute=_execute,
)
