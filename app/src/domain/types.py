from enum import StrEnum


class AgentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class ItemType(StrEnum):
    MESSAGE = "message"
    FUNCTION_CALL = "function_call"
    FUNCTION_CALL_OUTPUT = "function_call_output"


class WaitType(StrEnum):
    TOOL_RESULT = "tool_result"


class ToolType(StrEnum):
    SYNC = "sync"
    HUMAN = "human"
    # TODO: AGENT = "agent"
