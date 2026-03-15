import json
import logging

from openai import AsyncOpenAI

from src.config import settings
from .types import ProviderMessage, ProviderResponse, ProviderToolCall

logger = logging.getLogger(__name__)


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
        response = await self._client.chat.completions.create(**kwargs)
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
