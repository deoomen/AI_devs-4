from dataclasses import dataclass, field
from .types import AgentStatus, WaitType


@dataclass
class WaitEntry:
    call_id: str
    tool_name: str
    type: WaitType = WaitType.TOOL_RESULT


@dataclass
class AgentConfig:
    name: str
    model: str
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    max_turns: int = 10


@dataclass
class Agent:
    id: str
    session_id: str
    status: AgentStatus
    config: AgentConfig
    turn_count: int = 0
    waiting_for: list[WaitEntry] = field(default_factory=list)
    workspace_path: str | None = None
    parent_agent_id: str | None = None


# Pure state transitions

def start_agent(agent: Agent) -> Agent:
    agent.status = AgentStatus.RUNNING
    return agent


def wait_for(agent: Agent, entries: list[WaitEntry]) -> Agent:
    agent.status = AgentStatus.WAITING
    agent.waiting_for = entries
    return agent


def deliver_one(agent: Agent, call_id: str) -> Agent:
    agent.waiting_for = [w for w in agent.waiting_for if w.call_id != call_id]
    if not agent.waiting_for:
        agent.status = AgentStatus.RUNNING
    return agent


def complete_agent(agent: Agent, failed: bool = False) -> Agent:
    agent.status = AgentStatus.FAILED if failed else AgentStatus.COMPLETED
    agent.waiting_for = []
    return agent
