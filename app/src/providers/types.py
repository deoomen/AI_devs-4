import json
from dataclasses import dataclass, field
from typing import Protocol, TypeAlias


CHARS_PER_TOKEN = 3.5  # ~4 chars per token for English text

# Content types — mirrors TS `Content = string | ContentPart[]`
ContentPart: TypeAlias = dict  # {"type": "text", "text": "..."} | {"type": "image_url", "image_url": {"url": "..."}}
Content: TypeAlias = str | list[ContentPart]


@dataclass
class ProviderMessage:
    role: str
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


def _estimate_content_chars(content: Content | None) -> int:
    """Estimate character count for content (text or multimodal)."""
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content)
    chars = 0
    for part in content:
        if part.get("type") == "text":
            chars += len(part.get("text", ""))
        elif part.get("type") == "image_url":
            chars += 1000  # rough estimate for image tokens
    return chars


def estimate_tokens(
    messages: list[ProviderMessage],
    tools: list[dict] | None = None,
) -> int:
    """Rough pre-request token estimate. ~4 chars/token for English text."""
    chars = 0
    for msg in messages:
        chars += _estimate_content_chars(msg.content)
        if msg.tool_calls:
            chars += len(json.dumps(msg.tool_calls))
        chars += 20  # overhead per message (role tags, separators)
    if tools:
        chars += len(json.dumps(tools))
    return int(chars / CHARS_PER_TOKEN)
