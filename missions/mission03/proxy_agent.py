import json
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel

from config import load_config
from services.OpenRouter import OpenRouterClient
from services.SessionStore import SessionStore

SESSIONS_DIR = Path(__file__).parent / ".sessions"
MAX_TOOL_ITERATIONS = 5
MODEL = "openai/gpt-4o-mini"

SYSTEM_PROMPT = "You are a helpful proxy agent. Answer concisely and use tools when needed."

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": "Returns the current date and time in ISO 8601 format.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


async def execute_tool(name: str, args: dict) -> str:
    if name == "get_current_datetime":
        return datetime.now().isoformat()
    return f"Unknown tool: {name}"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class OperatorMessage(BaseModel):
    sessionID: str
    msg: str


class AgentMessage(BaseModel):
    msg: str


session_store = SessionStore(SESSIONS_DIR)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class ProxyAgent:
    def __init__(self):
        config = load_config()
        self._llm = OpenRouterClient(api_key=config.openrouter_api_key, default_model=MODEL)

    async def handle_message(self, message: OperatorMessage) -> AgentMessage:
        session_store.add_message(message.sessionID, "user", message.msg)

        # Build messages for LLM: system + full history (already includes new user msg)
        history = session_store.get_history(message.sessionID)
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += [{"role": m.role, "content": m.content} for m in history]

        for _ in range(MAX_TOOL_ITERATIONS):
            choice = await self._llm.chat_with_tools(messages=messages, tools=TOOLS)

            if choice.finish_reason == "tool_calls":
                assistant_msg = choice.message
                # Append assistant message with tool_calls to in-memory messages
                messages.append(assistant_msg.model_dump(exclude_unset=True))

                for tool_call in assistant_msg.tool_calls:
                    result = await execute_tool(
                        tool_call.function.name,
                        json.loads(tool_call.function.arguments),
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })
            else:
                text = choice.message.content or ""
                session_store.add_message(message.sessionID, "assistant", text)
                return AgentMessage(msg=text)

        fallback = "Max tool iterations reached without a final response."
        session_store.add_message(message.sessionID, "assistant", fallback)
        return AgentMessage(msg=fallback)
