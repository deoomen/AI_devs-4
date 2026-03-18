import uuid

from loguru import logger

from src.domain.agent import Agent
from src.domain.entry import Entry
from src.domain.types import AgentStatus, EntryType, Role, ToolType
from src.runtime.context import get_runtime_context
from src.tools.workspace import get_workspace_root
from src.workspace.loader import list_agent_names, load_agent_config
from ..types import Tool, ToolDefinition, ToolResult


def _build_description() -> str:
    from src.config import settings
    base = (
        "Spawn a subagent to handle a task autonomously. "
        "The subagent runs to completion and shares the same workspace (files are accessible to both). "
        "Returns the subagent's final text output."
    )
    agents = []
    for name in list_agent_names():
        # Exclude the main orchestrator agent
        if name == settings.agent_default_name:
            continue
        config = load_agent_config(name)
        if config is None:
            continue
        if config.description:
            agents.append(f"{name} — {config.description}")
        else:
            agents.append(name)
    if agents:
        base += " Available agents: " + "; ".join(agents) + "."
    return base


def _extract_last_assistant_text(entries: list[Entry]) -> str | None:
    for entry in reversed(entries):
        if entry.type == EntryType.MESSAGE and entry.role == Role.ASSISTANT and entry.content:
            return entry.content
    return None


async def _execute(arguments: dict) -> ToolResult:
    agent_name = arguments.get("agent_name", "")
    message = arguments.get("message", "")

    if not agent_name:
        return ToolResult(output="Missing agent_name", is_error=True)
    if not message:
        return ToolResult(output="Missing message", is_error=True)

    ctx = get_runtime_context()
    if ctx is None:
        return ToolResult(output="No runtime context available", is_error=True)

    # Prevent spawning the main orchestrator agent
    from src.config import settings
    if agent_name == settings.agent_default_name:
        return ToolResult(output=f"Cannot spawn the main agent ('{agent_name}')", is_error=True)

    config = load_agent_config(agent_name)
    if config is None:
        return ToolResult(output=f"Agent '{agent_name}' not found", is_error=True)

    # Reuse parent's workspace so files are shared
    workspace = ctx.agent_workspace or get_workspace_root()

    agent_id = str(uuid.uuid4())
    agent = Agent(
        id=agent_id,
        session_id=ctx.session_id,
        status=AgentStatus.PENDING,
        config=config,
        workspace_path=str(workspace),
        parent_agent_id=ctx.agent_id,
    )
    await ctx.repos.agents.create(agent)

    # Add user message
    seq = await ctx.repos.entries.next_sequence(agent_id)
    entry = Entry(
        id=str(uuid.uuid4()),
        session_id=ctx.session_id,
        agent_id=agent_id,
        turn=0,
        sequence=seq,
        type=EntryType.MESSAGE,
        role=Role.USER,
        content=message,
    )
    await ctx.repos.entries.create(entry)

    logger.info("Spawning subagent '{}' (id={})", agent_name, agent_id)

    # Run subagent to completion
    from src.runtime.runner import run_agent
    agent = await run_agent(ctx, agent, user_id="subagent")

    entries = await ctx.repos.entries.list_by_agent(agent.id)
    output = _extract_last_assistant_text(entries)

    if agent.status == AgentStatus.COMPLETED:
        logger.info("Subagent '{}' completed", agent_name)
        return ToolResult(output=output or "(no output)")
    else:
        logger.warning("Subagent '{}' ended with status={}", agent_name, agent.status)
        return ToolResult(
            output=f"Subagent ended with status={agent.status}. Last output: {output or '(none)'}",
            is_error=True,
        )


spawn_agent_tool = Tool(
    name="spawn_agent",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="spawn_agent",
        description=_build_description(),
        parameters={
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Name of the agent config to use (e.g. 'bob')",
                },
                "message": {
                    "type": "string",
                    "description": "Task message to send to the subagent",
                },
            },
            "required": ["agent_name", "message"],
        },
    ),
    execute=_execute,
)
