from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ProviderMessage:
    role: str
    content: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


@dataclass
class ProviderToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ProviderResponse:
    content: str | None = None
    tool_calls: list[ProviderToolCall] = field(default_factory=list)
    finish_reason: str = "stop"


class Provider(Protocol):
    async def chat(
        self,
        model: str,
        messages: list[ProviderMessage],
        tools: list[dict] | None = None,
    ) -> ProviderResponse: ...
