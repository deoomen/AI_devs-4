import asyncio
import json

import httpx
from loguru import logger

from src.config import settings
from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult

DEFAULT_TIMEOUT = 30.0


async def _execute(arguments: dict) -> ToolResult:
    endpoint = arguments.get("endpoint", "/verify")
    task = arguments.get("task", "")
    answer = arguments.get("answer")

    if not task:
        return ToolResult(output="Missing task name", is_error=True)

    url = f"{settings.aidevs4_headquarters_system_url}{endpoint}"
    payload = {
        "apikey": settings.aidevs4_headquarters_api_key,
        "task": task,
        "answer": answer,
    }

    logger.info("headquarters {} task={}", endpoint, task)

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(url, json=payload)
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

    logger.info("headquarters response: {} {}", response.status_code, body_str[:200])

    # Respect retry_after from response body on 429
    if response.status_code == 429 and isinstance(result, dict):
        retry_after = result.get("retry_after")
        if retry_after:
            wait = int(retry_after) + 1  # +1s safety margin
            logger.info("Headquarters rate limited, waiting {}s before returning", wait)
            await asyncio.sleep(wait)
            # Retry the same request after waiting
            try:
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                    response = await client.post(url, json=payload)
                try:
                    result = response.json()
                    body_str = json.dumps(result, ensure_ascii=False)
                except (json.JSONDecodeError, ValueError):
                    body_str = response.text
                logger.info("headquarters retry response: {} {}", response.status_code, body_str[:200])
            except (httpx.TimeoutException, httpx.RequestError) as e:
                return ToolResult(output=f"Retry failed: {e}", is_error=True)

    output = f"HTTP {response.status_code}\n{body_str}"
    return ToolResult(output=output, is_error=response.status_code >= 400)


aidevs_headquarters_tool = Tool(
    name="aidevs_headquarters",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="aidevs_headquarters",
        description="Communicate with the AIDevs headquarters. Use this to send mission answers via /verify or interact with any headquarters endpoint. The API key is injected automatically.",
        parameters={
            "type": "object",
            "properties": {
                "endpoint": {
                    "type": "string",
                    "description": "API endpoint path (default: /verify)",
                    "default": "/verify",
                },
                "task": {
                    "type": "string",
                    "description": "Task name (e.g. 'railway', 'poligon')",
                },
                "answer": {
                    "description": "The answer payload — can be a string, number, object, or array depending on the task",
                },
            },
            "required": ["task", "answer"],
        },
    ),
    execute=_execute,
)
