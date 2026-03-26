import shutil
from pathlib import Path

from loguru import logger

from src.config import to_relative_workspace
from src.domain.agent import Agent
from src.domain.entry import Entry
from src.domain.ids import AgentId, EntryId
from src.domain.types import AgentStatus, EntryType, Role, ToolType
from src.runtime.context import get_runtime_context
from src.tools.workspace import get_workspace_root, set_workspace_root
from src.workspace.loader import list_agent_names, load_agent_config
from src.workspace.session import SessionWorkspace
from ..types import Tool, ToolDefinition, ToolResult

_INLINE_MAX_BYTES = 2048


def _build_description() -> str:
    from src.config import settings
    base = (
        "Spawn a subagent to handle a task autonomously. "
        "The subagent gets its own isolated workspace. "
        "Pass files via input_files; results appear in your inbox/agnt_{id}/. "
        "Returns the subagent's final text output plus a manifest of produced files."
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


def _copy_input_files(input_files: list[str], parent_workspace: Path, child_inbox: Path) -> list[str]:
    """Copy parent workspace files into child's inbox. Returns list of copied filenames."""
    copied = []
    for rel_path in input_files:
        src = (parent_workspace / rel_path).resolve()
        # Security: ensure source is within parent workspace
        if not str(src).startswith(str(parent_workspace.resolve())):
            logger.warning("input_files path escapes parent workspace: {}", rel_path)
            continue
        if not src.is_file():
            logger.warning("input_files source not found: {}", src)
            continue
        dst = child_inbox / Path(rel_path).name
        shutil.copy2(src, dst)
        copied.append(dst.name)
    return copied


def _copy_outbox_to_parent_inbox(
    child_outbox: Path, parent_workspace: Path, short_id: str,
) -> list[str]:
    """Copy child outbox files into parent's inbox/agnt_{short_id}/. Returns filenames."""
    if not child_outbox.is_dir():
        return []
    files = [f for f in child_outbox.iterdir() if f.is_file()]
    if not files:
        return []
    parent_inbox = parent_workspace / "inbox" / f"agnt_{short_id}"
    parent_inbox.mkdir(parents=True, exist_ok=True)
    copied = []
    for f in files:
        shutil.copy2(f, parent_inbox / f.name)
        copied.append(f.name)
    return copied


def _build_result_text(
    short_id: str,
    output: str | None,
    bridged_files: list[str],
) -> str:
    """Build enhanced tool result with output and file manifest."""
    parts = [output or "(no output)"]
    if bridged_files:
        inbox_prefix = f"inbox/agnt_{short_id}"
        parts.append(f"\n--- Files available in {inbox_prefix}/ ---")
        for name in bridged_files:
            file_path = f"{inbox_prefix}/{name}"
            parts.append(f"  {file_path}")
    return "\n".join(parts)


async def _execute(arguments: dict) -> ToolResult:
    agent_name = arguments.get("agent_name", "")
    message = arguments.get("message", "")
    input_files: list[str] = arguments.get("input_files", [])

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

    # Save parent context (relative paths)
    parent_rel = ctx.agent_workspace
    parent_abs = get_workspace_root()  # resolved absolute for file I/O
    parent_agent_id = ctx.agent_id

    # Create isolated child workspace
    ws = SessionWorkspace(ctx.session_id)
    agent_id = AgentId.generate()
    short_id = agent_id.short()
    child_abs = ws.create_agent_dir(agent_id)
    child_rel = to_relative_workspace(child_abs)

    # Copy input files from parent workspace into child's inbox
    if input_files:
        copied = _copy_input_files(input_files, parent_abs, child_abs / "inbox")
        if copied:
            logger.info("Copied {} input file(s) to child inbox: {}", len(copied), copied)

    agent = Agent(
        id=agent_id,
        session_id=ctx.session_id,
        status=AgentStatus.PENDING,
        config=config,
        workspace_path=child_rel,
        parent_agent_id=ctx.agent_id,
    )
    await ctx.repos.agents.create(agent)

    # Add user message
    seq = await ctx.repos.entries.next_sequence(agent_id)
    entry = Entry(
        id=EntryId.generate(),
        session_id=ctx.session_id,
        agent_id=agent_id,
        turn=0,
        sequence=seq,
        type=EntryType.MESSAGE,
        role=Role.USER,
        content=message,
    )
    await ctx.repos.entries.create(entry)

    logger.info("Spawning subagent '{}' (id={}) with isolated workspace", agent_name, agent_id)

    # Set child workspace on context and run subagent
    ctx.agent_workspace = child_rel
    from src.runtime.runner import run_agent
    agent = await run_agent(ctx, agent)

    # Restore parent context
    ctx.agent_workspace = parent_rel
    ctx.agent_id = parent_agent_id
    if parent_rel:
        set_workspace_root(parent_rel)

    # Bridge: copy child outbox → parent inbox
    bridged_files = _copy_outbox_to_parent_inbox(
        child_abs / "outbox", parent_abs, short_id,
    )
    if bridged_files:
        logger.info("Bridged {} file(s) from child outbox to parent inbox", len(bridged_files))

    # Clean up child workspace after bridging is complete
    if settings.agent_cleanup_child_workspace:
        shutil.rmtree(child_abs, ignore_errors=True)
        logger.info("Cleaned up child workspace: {}", child_abs)

    entries = await ctx.repos.entries.list_by_agent(agent.id)
    output = _extract_last_assistant_text(entries)

    result_text = _build_result_text(short_id, output, bridged_files)

    if agent.status == AgentStatus.COMPLETED:
        logger.info("Subagent '{}' completed", agent_name)
        return ToolResult(output=result_text)
    else:
        logger.warning("Subagent '{}' ended with status={}", agent_name, agent.status)
        return ToolResult(
            output=f"Subagent ended with status={agent.status}. {result_text}",
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
                "input_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional list of relative paths in your workspace to copy "
                        "into the subagent's inbox (e.g. ['outbox/data.csv', 'notes/plan.md'])"
                    ),
                },
            },
            "required": ["agent_name", "message"],
        },
    ),
    execute=_execute,
)
