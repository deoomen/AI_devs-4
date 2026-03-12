import instructor
import logging
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel
from typing import TypeVar

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class OpenRouterClient:
    def __init__(self, api_key: str, default_model: str = "openai/gpt-4o-mini"):
        self.default_model = default_model
        self._openai = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self._instructor = instructor.from_openai(self._openai)

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> str:
        response = await self._openai.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
        )
        content = response.choices[0].message.content
        log.debug("OpenRouter response: %s", content)
        return content

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
    ):
        response = await self._openai.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        choice = response.choices[0]
        log.debug("OpenRouter tool response: finish_reason=%s", choice.finish_reason)
        return choice

    async def chat_structured(
        self,
        messages: list[dict],
        response_model: type[T],
        model: str | None = None,
    ) -> T:
        result = await self._instructor.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            response_model=response_model,
        )
        log.debug("OpenRouter structured response: %s", result)
        return result
