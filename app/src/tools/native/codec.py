import base64
import hashlib
import urllib.parse
import codecs

from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult

_ONE_WAY = {"sha1", "sha256", "sha512", "md5"}

_HASH_FN = {
    "sha1": hashlib.sha1,
    "sha256": hashlib.sha256,
    "sha512": hashlib.sha512,
    "md5": hashlib.md5,
}


async def _execute(arguments: dict) -> ToolResult:
    algorithm = arguments.get("algorithm", "").lower().strip()
    operation = arguments.get("operation", "encode").lower().strip()
    text = arguments.get("input", "")

    if not algorithm:
        return ToolResult(output="Missing algorithm", is_error=True)
    if not text and text != "":
        return ToolResult(output="Missing input", is_error=True)
    if operation not in ("encode", "decode"):
        return ToolResult(output="operation must be 'encode' or 'decode'", is_error=True)
    if operation == "decode" and algorithm in _ONE_WAY:
        return ToolResult(output=f"{algorithm} is a one-way hash — decode is not possible", is_error=True)

    try:
        if algorithm in _HASH_FN:
            result = _HASH_FN[algorithm](text.encode()).hexdigest()

        elif algorithm == "base64":
            if operation == "encode":
                result = base64.b64encode(text.encode()).decode()
            else:
                result = base64.b64decode(text.encode()).decode()

        elif algorithm == "hex":
            if operation == "encode":
                result = text.encode().hex()
            else:
                result = bytes.fromhex(text).decode()

        elif algorithm == "url":
            if operation == "encode":
                result = urllib.parse.quote(text, safe="")
            else:
                result = urllib.parse.unquote(text)

        elif algorithm == "rot13":
            result = codecs.encode(text, "rot_13")

        else:
            return ToolResult(
                output=f"Unknown algorithm: '{algorithm}'. Supported: sha1, sha256, sha512, md5, base64, hex, url, rot13",
                is_error=True,
            )
    except Exception as e:
        return ToolResult(output=f"Codec error ({algorithm}/{operation}): {e}", is_error=True)

    return ToolResult(output=result)


codec_tool = Tool(
    name="codec",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="codec",
        description=(
            "Encode or decode a string using a common algorithm. "
            "One-way hash algorithms (sha1, sha256, sha512, md5) only support encode. "
            "Two-way algorithms (base64, hex, url, rot13) support both encode and decode."
        ),
        parameters={
            "type": "object",
            "properties": {
                "algorithm": {
                    "type": "string",
                    "description": "Algorithm to use: sha1 | sha256 | sha512 | md5 | base64 | hex | url | rot13",
                },
                "input": {
                    "type": "string",
                    "description": "The string to encode or decode",
                },
                "operation": {
                    "type": "string",
                    "enum": ["encode", "decode"],
                    "description": "Direction: 'encode' (default) or 'decode'. Hashes only support 'encode'.",
                },
            },
            "required": ["algorithm", "input"],
        },
    ),
    execute=_execute,
)
