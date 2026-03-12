from pydantic import BaseModel


class OperatorMessage(BaseModel):
    sessionID: str
    msg: str

class AgentMessage(BaseModel):
    msg: str

class ProxyAgent:
    async def handle_message(self, message: OperatorMessage) -> AgentMessage:
        return AgentMessage(msg="Sample response from proxy agent")
