from pydantic import BaseModel

from src.config import settings
from src.domain.ids import AgentId, SessionId


class ChatRequest(BaseModel):
    agent: str = settings.agent_default_name
    input: str
    session_id: SessionId | None = None


class DeliverRequest(BaseModel):
    call_id: str
    output: str


class AgentResponse(BaseModel):
    agent_id: AgentId
    status: str
    output: str | None = None
    waiting_for: list[dict] | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
