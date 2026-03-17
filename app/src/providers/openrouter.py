import asyncio
import json

from loguru import logger
from openai import AsyncOpenAI, RateLimitError

from src.config import settings
from .types import Content, Provider, ProviderMessage, ProviderResponse, ProviderToolCall, ProviderUsage


def _serialize_content(content: Content | None) -> str | list[dict]:
    """Convert Content to OpenAI-compatible format.

    Multimodal (list of parts) is passed through as-is;
    plain strings are returned directly.
    """
    if isinstance(content, list):
        return content
    return content or ""


class OpenRouterProvider(Provider):
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
                    "content": _serialize_content(msg.content),
                })

        kwargs: dict = {"model": model, "messages": openai_messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        logger.info("LLM request: model={} messages={} tools={}", model, len(openai_messages), len(tools or []))

        response, headers = await self._call_with_retry(kwargs)
        _log_rate_limits(headers, kwargs["model"])
        await _wait_if_rate_limited(headers, kwargs["model"])
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

        usage = None
        if response.usage:
            usage = ProviderUsage(
                input_tokens=response.usage.prompt_tokens or 0,
                output_tokens=response.usage.completion_tokens or 0,
                total_tokens=response.usage.total_tokens or 0,
            )

        return ProviderResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )

    async def _call_with_retry(self, kwargs: dict):
        for attempt in range(settings.provider_max_retries):
            try:
                raw = await self._client.chat.completions.with_raw_response.create(**kwargs)
                return raw.parse(), raw.headers
            except RateLimitError as e:
                retry_after = _parse_retry_after(e)
                if attempt == settings.provider_max_retries - 1:
                    raise
                logger.warning(
                    "Provider rate limited (attempt {}/{}), retrying in {:.1f}s",
                    attempt + 1, settings.provider_max_retries, retry_after,
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
        logger.info("Provider rate limits [{}]: {}", model, limits)


def _parse_reset_seconds(value: str) -> float | None:
    """Parse reset header value like '15s', '1m30s', or plain seconds."""
    if not value:
        return None
    # Plain number (seconds)
    try:
        return float(value)
    except ValueError:
        pass
    # Duration format like "15s", "1m30s"
    import re
    match = re.match(r"(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?", value)
    if match and (match.group(1) or match.group(2)):
        minutes = float(match.group(1) or 0)
        seconds = float(match.group(2) or 0)
        return minutes * 60 + seconds
    return None


async def _wait_if_rate_limited(headers, model: str) -> None:
    remaining = headers.get("x-ratelimit-remaining-requests")
    reset = headers.get("x-ratelimit-reset-requests")

    if remaining is not None and int(remaining) == 0 and reset:
        wait_seconds = _parse_reset_seconds(reset)
        if wait_seconds and wait_seconds > 0:
            logger.info(
                "Rate limit reached for [{}], waiting {:.1f}s before next call",
                model, wait_seconds,
            )
            await asyncio.sleep(wait_seconds)


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
