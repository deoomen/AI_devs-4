from dataclasses import dataclass, field
from typing import Protocol, TypeAlias

from src.domain.types import Role

# Content types — mirrors TS `Content = string | ContentPart[]`
ContentPart: TypeAlias = dict  # {"type": "text", "text": "..."} | {"type": "image_url", "image_url": {"url": "..."}}
Content: TypeAlias = str | list[ContentPart]


@dataclass
class ProviderMessage:
    role: Role
    content: Content | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


@dataclass
class ProviderToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ProviderUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int | None = None


@dataclass
class ProviderResponse:
    content: str | None = None
    tool_calls: list[ProviderToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: ProviderUsage | None = None
    model: str | None = None  # resolved model name (populated by provider)


class Provider(Protocol):
    async def chat(
        self,
        messages: list[ProviderMessage],
        model: str | None = None,
        tools: list[dict] | None = None,
    ) -> ProviderResponse: ...
