import json
from pathlib import Path
from pydantic import BaseModel
from typing import Literal

SESSIONS_DIR = Path(__file__).parent / ".sessions"


class OperatorMessage(BaseModel):
    sessionID: str
    msg: str


class AgentMessage(BaseModel):
    msg: str


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class SessionStore:
    def __init__(self, sessions_dir: Path = SESSIONS_DIR):
        self._dir = sessions_dir
        self._dir.mkdir(exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self._dir / f"{session_id}.json"

    def get_history(self, session_id: str) -> list[Message]:
        path = self._path(session_id)
        if not path.exists():
            return []
        return [Message(**m) for m in json.loads(path.read_text())]

    def add_message(self, session_id: str, role: Literal["user", "assistant"], content: str) -> None:
        history = self.get_history(session_id)
        history.append(Message(role=role, content=content))
        self._path(session_id).write_text(
            json.dumps([m.model_dump() for m in history], ensure_ascii=False, indent=2)
        )


session_store = SessionStore()


class ProxyAgent:
    async def handle_message(self, message: OperatorMessage) -> AgentMessage:
        session_store.add_message(message.sessionID, "user", message.msg)

        history = session_store.get_history(message.sessionID)
        response = f"[session={message.sessionID}, turn={len(history)}] Sample response from proxy agent"

        session_store.add_message(message.sessionID, "assistant", response)
        return AgentMessage(msg=response)
