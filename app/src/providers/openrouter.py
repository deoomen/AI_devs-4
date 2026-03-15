import asyncio
import json
import logging

from openai import AsyncOpenAI, RateLimitError

from src.config import settings
from .types import ProviderMessage, ProviderResponse, ProviderToolCall

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


class OpenRouterProvider:
    def __init__(self):
        self._client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
        )

    async def chat(
        self,
        model: str,
        messages: list[ProviderMessage],
        tools: list[dict] | None = None,
    ) -> ProviderResponse:
        openai_messages = []
        for msg in messages:
            if msg.tool_call_id:
                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content or "",
                })
            elif msg.tool_calls:
                openai_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                    "tool_calls": msg.tool_calls,
                })
            else:
                openai_messages.append({
                    "role": msg.role,
                    "content": msg.content or "",
                })

        kwargs: dict = {"model": model, "messages": openai_messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        logger.debug("LLM request: model=%s messages=%d tools=%d", model, len(openai_messages), len(tools or []))

        response, headers = await self._call_with_retry(kwargs)
        _log_rate_limits(headers, kwargs["model"])
        choice = response.choices[0]

        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(ProviderToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        return ProviderResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
        )

    async def _call_with_retry(self, kwargs: dict):
        for attempt in range(MAX_RETRIES):
            try:
                raw = await self._client.chat.completions.with_raw_response.create(**kwargs)
                return raw.parse(), raw.headers
            except RateLimitError as e:
                retry_after = _parse_retry_after(e)
                if attempt == MAX_RETRIES - 1:
                    raise
                logger.warning(
                    "Provider rate limited (attempt %d/%d), retrying in %.1fs",
                    attempt + 1, MAX_RETRIES, retry_after,
                )
                await asyncio.sleep(retry_after)


_RATE_LIMIT_HEADERS = [
    "x-ratelimit-limit-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-remaining-tokens",
    "x-ratelimit-reset-requests",
    "x-ratelimit-reset-tokens",
]


def _log_rate_limits(headers, model: str) -> None:
    limits = {h: headers.get(h) for h in _RATE_LIMIT_HEADERS if headers.get(h)}
    if limits:
        logger.debug("Provider rate limits [%s]: %s", model, limits)


def _parse_retry_after(error: RateLimitError) -> float:
    headers = getattr(error, "response", None)
    if headers is not None:
        headers = getattr(headers, "headers", {})
        retry_after = headers.get("retry-after") or headers.get("x-ratelimit-reset")
        if retry_after:
            try:
                return max(float(retry_after), 1.0)
            except ValueError:
                pass
    return 5.0
