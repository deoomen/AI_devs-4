from src.domain.types import ToolType
from .types import Tool, ToolDefinition

ask_user_tool = Tool(
    name="ask_user",
    type=ToolType.HUMAN,
    definition=ToolDefinition(
        name="ask_user",
        description="Ask the user a question and wait for their response. Use this when you need clarification or additional information from the user.",
        parameters={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask the user",
                },
            },
            "required": ["question"],
        },
    ),
    execute=None,  # HUMAN tools don't execute — runner handles them
)
