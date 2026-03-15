from pydantic import BaseModel


class ChatRequest(BaseModel):
    agent: str = "alice"
    input: str
    session_id: str | None = None


class DeliverRequest(BaseModel):
    call_id: str
    output: str


class AgentResponse(BaseModel):
    agent_id: str
    status: str
    output: str | None = None
    waiting_for: list[dict] | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
