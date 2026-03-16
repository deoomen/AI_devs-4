import json
from dataclasses import dataclass, field
from typing import Protocol

CHARS_PER_TOKEN = 3.5  # ~4 chars per token for English text


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


class Provider(Protocol):
    async def chat(
        self,
        model: str,
        messages: list[ProviderMessage],
        tools: list[dict] | None = None,
    ) -> ProviderResponse: ...


def estimate_tokens(
    messages: list[ProviderMessage],
    tools: list[dict] | None = None,
) -> int:
    """Rough pre-request token estimate. ~4 chars/token for English text."""
    chars = 0
    for msg in messages:
        chars += len(msg.content or "")
        if msg.tool_calls:
            chars += len(json.dumps(msg.tool_calls))
        chars += 20  # overhead per message (role tags, separators)
    if tools:
        chars += len(json.dumps(tools))
    return int(chars / CHARS_PER_TOKEN)
