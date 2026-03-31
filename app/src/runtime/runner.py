import json
import time

from src.domain.agent import (
    Agent,
    WaitEntry,
    complete_agent,
    deliver_one,
    start_agent,
    wait_for,
)
from src.domain.entry import Entry
from src.domain.ids import AgentId, EntryId, SessionId
from src.domain.types import AgentStatus, EntryType, Role, ToolType, WaitType
from loguru import logger

from src.events.types import Event, EventName
from src.providers.types import ProviderMessage
from src.utils.tokens import estimate_tokens
from src.tools.workspace import set_workspace_root
from src.config import settings
from .context import RuntimeContext, set_runtime_context


def _entries_to_messages(entries: list[Entry], system_prompt: str) -> list[ProviderMessage]:
    messages = [ProviderMessage(role=Role.SYSTEM, content=system_prompt)]
    for entry in entries:
        if entry.type == EntryType.MESSAGE:
            messages.append(ProviderMessage(role=entry.role, content=entry.content))
        elif entry.type == EntryType.FUNCTION_CALL:
            messages.append(ProviderMessage(
                role=entry.role,
                content=None,
                tool_calls=[{
                    "id": entry.call_id,
                    "type": "function",
                    "function": {
                        "name": entry.name,
                        "arguments": json.dumps(entry.arguments or {}),
                    },
                }],
            ))
        elif entry.type == EntryType.FUNCTION_CALL_OUTPUT:
            messages.append(ProviderMessage(
                role=entry.role,
                content=entry.output or "",
                tool_call_id=entry.call_id,
            ))
    return messages


def _messages_to_dicts(messages: list[ProviderMessage]) -> list[dict]:
    """Serialize ProviderMessage list to plain dicts for event data / Langfuse input."""
    result = []
    for m in messages:
        if m.tool_call_id:
            result.append({"role": Role.TOOL, "tool_call_id": m.tool_call_id, "content": m.content or ""})
        elif m.tool_calls:
            result.append({"role": m.role, "content": m.content, "tool_calls": m.tool_calls})
        else:
            result.append({"role": m.role, "content": m.content or ""})
    return result


def _bind_log_context(session_id: SessionId, agent_id: AgentId, agent_name: str) -> None:
    """Bind session/agent info to loguru context for all subsequent log calls."""
    logger.configure(extra={
        "session_id": session_id.short(),
        "agent_id": agent_id.short(),
        "agent_name": agent_name,
    })


async def _store_entry(ctx: RuntimeContext, agent_id: AgentId, turn: int, **kwargs) -> Entry:
    seq = await ctx.repos.entries.next_sequence(agent_id)
    entry = Entry(id=EntryId.generate(), session_id=ctx.session_id, agent_id=agent_id, turn=turn, sequence=seq, **kwargs)
    await ctx.repos.entries.create(entry)
    return entry


async def run_agent(
    ctx: RuntimeContext,
    agent: Agent,
    user_input: str = "",
) -> Agent:
    """Main agent loop. Returns agent in COMPLETED or WAITING state."""
    ctx.agent_id = agent.id
    set_runtime_context(ctx)
    _bind_log_context(ctx.session_id, agent.id, agent.config.name)
    if ctx.agent_workspace:
        set_workspace_root(ctx.agent_workspace)

    if agent.status == AgentStatus.PENDING:
        agent = start_agent(agent)
        await ctx.repos.agents.update(agent)
        ctx.events.emit(Event(
            name=EventName.AGENT_STARTED,
            agent_id=agent.id,
            data={
                "agent_name": agent.config.name,
                "model": agent.config.model,
                "session_id": str(agent.session_id),
                "user_id": str(ctx.user_id) if ctx.user_id else None,
                "user_input": user_input,
            },
        ))

    tool_defs = ctx.tools.get_definitions(agent.config.tools or None)
    max_turns = agent.config.max_turns

    while agent.turn_count < max_turns:
        entries = await ctx.repos.entries.list_by_agent(agent.id)
        messages = _entries_to_messages(entries, agent.config.system_prompt)

        ctx.events.emit(Event(
            name=EventName.TURN_START,
            agent_id=agent.id,
            data={"turn": agent.turn_count, "entries": len(entries)},
        ))

        estimated = estimate_tokens(messages, tool_defs or None)
        logger.info("Turn {} | ~{} tokens | {} messages", agent.turn_count, estimated, len(messages))

        # Log system prompt on first turn only
        if agent.turn_count == 0:
            logger.info("System prompt: {}…", agent.config.system_prompt)

        # Log the last message being sent (user input or tool result)
        last = messages[-1]
        logger.info("Last message: role={} | {}", last.role, (last.content or ""))

        # ── LLM call with timing ──────────────────────────────────────────────
        ctx.events.emit(Event(
            name=EventName.GENERATION_STARTED,
            agent_id=agent.id,
            data={
                "turn": agent.turn_count,
                "model": agent.config.model,
                "input": _messages_to_dicts(messages),
            },
        ))
        gen_start = time.time()
        response = await ctx.provider.chat(
            messages=messages,
            model=agent.config.model or None,
            tools=tool_defs or None,
        )
        gen_duration_ms = int((time.time() - gen_start) * 1000)

        logger.info("LLM response: finish={} | {}", response.finish_reason, (response.content or ""))

        if response.usage:
            logger.info(
                "Actual usage: in={} out={} total={} cached={}",
                response.usage.input_tokens, response.usage.output_tokens,
                response.usage.total_tokens, response.usage.cached_tokens,
            )

        ctx.events.emit(Event(
            name=EventName.GENERATION_COMPLETED,
            agent_id=agent.id,
            data={
                "model": response.model,
                "input": _messages_to_dicts(messages),
                "output": response.content or "",
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.total_tokens,
                } if response.usage else None,
                "finish_reason": response.finish_reason,
                "turn": agent.turn_count,
                "start_time": gen_start,
                "duration_ms": gen_duration_ms,
            },
        ))

        # Store assistant text if present
        if response.content:
            await _store_entry(
                ctx, agent.id, turn=agent.turn_count,
                type=EntryType.MESSAGE,
                role=Role.ASSISTANT,
                content=response.content,
            )

        # Store function calls
        for tc in response.tool_calls:
            await _store_entry(
                ctx, agent.id, turn=agent.turn_count,
                type=EntryType.FUNCTION_CALL,
                role=Role.ASSISTANT,
                call_id=tc.id,
                name=tc.name,
                arguments=tc.arguments,
            )

        # Process tool calls
        human_waits: list[WaitEntry] = []
        for tc in response.tool_calls:
            tool = ctx.tools.get(tc.name)
            if tool is None:
                await _store_entry(
                    ctx, agent.id, turn=agent.turn_count,
                    type=EntryType.FUNCTION_CALL_OUTPUT,
                    role=Role.TOOL,
                    call_id=tc.id,
                    name=tc.name,
                    output=f"Unknown tool: {tc.name}",
                    is_error=True,
                )
                continue

            if tool.type == ToolType.HUMAN:
                human_waits.append(WaitEntry(
                    call_id=tc.id,
                    tool_name=tc.name,
                    type=WaitType.TOOL_RESULT,
                    arguments=tc.arguments or {},
                ))
                ctx.events.emit(Event(
                    name=EventName.TOOL_HUMAN_REQUESTED,
                    agent_id=agent.id,
                    data={"call_id": tc.id, "tool": tc.name, "arguments": tc.arguments},
                ))
            else:
                # ── Tool call with timing ─────────────────────────────────────
                ctx.events.emit(Event(
                    name=EventName.TOOL_STARTED,
                    agent_id=agent.id,
                    data={"call_id": tc.id, "name": tc.name, "arguments": tc.arguments},
                ))
                tool_start = time.time()
                result = await ctx.tools.execute(tc.name, tc.arguments)
                tool_duration_ms = int((time.time() - tool_start) * 1000)

                await _store_entry(
                    ctx, agent.id, turn=agent.turn_count,
                    type=EntryType.FUNCTION_CALL_OUTPUT,
                    role=Role.TOOL,
                    call_id=tc.id,
                    name=tc.name,
                    output=result.output,
                    is_error=result.is_error,
                )
                ctx.events.emit(Event(
                    name=EventName.TOOL_COMPLETED,
                    agent_id=agent.id,
                    data={
                        "name": tc.name,
                        "call_id": tc.id,
                        "arguments": tc.arguments,
                        "output": result.output,
                        "is_error": result.is_error,
                        "start_time": tool_start,
                        "duration_ms": tool_duration_ms,
                    },
                ))

        if human_waits:
            agent = wait_for(agent, human_waits)
            await ctx.repos.agents.update(agent)
            ctx.events.emit(Event(
                name=EventName.AGENT_WAITING,
                agent_id=agent.id,
                data={"waiting_for": [w.call_id for w in human_waits]},
            ))
            return agent

        agent.turn_count += 1
        await ctx.repos.agents.update(agent)

        # If no tool calls, we're done
        if not response.tool_calls:
            break
    else:
        logger.warning("Agent hit max turn limit ({})", max_turns)

    reached_max_turns = agent.turn_count >= max_turns
    agent = complete_agent(agent)
    await ctx.repos.agents.update(agent)

    # Collect final output for the trace
    entries = await ctx.repos.entries.list_by_agent(agent.id)
    last_text = next(
        (e.content for e in reversed(entries) if e.type == EntryType.MESSAGE and e.role == Role.ASSISTANT and e.content),
        None,
    )
    if reached_max_turns:
        final_text = settings.agent_max_turn_final_text
    else:
        final_text = last_text or settings.agent_fallback_final_text
    ctx.events.emit(Event(
        name=EventName.AGENT_COMPLETED,
        agent_id=agent.id,
        data={"output": final_text},
    ))
    return agent


async def deliver_result(ctx: RuntimeContext, agent: Agent, call_id: str, output: str) -> Agent:
    """Deliver a tool result to a waiting agent, then resume the loop."""
    await _store_entry(
        ctx, agent.id, turn=agent.turn_count,
        type=EntryType.FUNCTION_CALL_OUTPUT,
        role=Role.TOOL,
        call_id=call_id,
        output=output,
    )

    agent = deliver_one(agent, call_id)
    await ctx.repos.agents.update(agent)

    if agent.status == AgentStatus.RUNNING:
        ctx.events.emit(Event(name=EventName.AGENT_RESUMED, agent_id=agent.id))
        return await run_agent(ctx, agent)

    return agent
