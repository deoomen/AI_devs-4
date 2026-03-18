import json
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from src.providers.types import Content, ProviderMessage

CHARS_PER_TOKEN = 3.2  # conservative estimate (~overcounts slightly)


def _estimate_content_chars(content: "Content | None") -> int:
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


@overload
def estimate_tokens(input: str) -> int: ...
@overload
def estimate_tokens(input: "list[ProviderMessage]", tools: list[dict] | None = None) -> int: ...


def estimate_tokens(input, tools=None) -> int:
    """Estimate token count for plain text or LLM messages + tool definitions."""
    if isinstance(input, str):
        return int(len(input) / CHARS_PER_TOKEN)

    chars = 0
    for msg in input:
        chars += _estimate_content_chars(msg.content)
        if msg.tool_calls:
            chars += len(json.dumps(msg.tool_calls))
        chars += 20  # overhead per message (role tags, separators)
    if tools:
        chars += len(json.dumps(tools))
    return int(chars / CHARS_PER_TOKEN)
