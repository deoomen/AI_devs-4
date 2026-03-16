import json
import logging
import uuid

from src.domain.agent import (
    Agent,
    WaitEntry,
    complete_agent,
    deliver_one,
    start_agent,
    wait_for,
)
from src.domain.item import Item
from src.domain.types import AgentStatus, ItemType, ToolType, WaitType
from src.events.types import Event
from src.providers.types import ProviderMessage, estimate_tokens
from src.tools.workspace import set_workspace_root
from .context import RuntimeContext

logger = logging.getLogger(__name__)


def _items_to_messages(items: list[Item], system_prompt: str) -> list[ProviderMessage]:
    messages = [ProviderMessage(role="system", content=system_prompt)]
    for item in items:
        if item.type == ItemType.MESSAGE:
            messages.append(ProviderMessage(role=item.role or "user", content=item.content))
        elif item.type == ItemType.FUNCTION_CALL:
            messages.append(ProviderMessage(
                role="assistant",
                content=None,
                tool_calls=[{
                    "id": item.call_id,
                    "type": "function",
                    "function": {
                        "name": item.name,
                        "arguments": json.dumps(item.arguments or {}),
                    },
                }],
            ))
        elif item.type == ItemType.FUNCTION_CALL_OUTPUT:
            messages.append(ProviderMessage(
                role="tool",
                content=item.output or "",
                tool_call_id=item.call_id,
            ))
    return messages


async def _store_item(ctx: RuntimeContext, agent_id: str, **kwargs) -> Item:
    seq = await ctx.repos.items.next_sequence(agent_id)
    item = Item(id=str(uuid.uuid4()), agent_id=agent_id, sequence=seq, **kwargs)
    await ctx.repos.items.create(item)
    return item


async def run_agent(ctx: RuntimeContext, agent: Agent) -> Agent:
    """Main agent loop. Returns agent in COMPLETED or WAITING state."""
    if ctx.agent_workspace:
        set_workspace_root(ctx.agent_workspace)

    if agent.status == AgentStatus.PENDING:
        agent = start_agent(agent)
        await ctx.repos.agents.update(agent)
        ctx.events.emit(Event(name="agent.started", agent_id=agent.id))

    tool_defs = ctx.tools.get_definitions(agent.config.tools or None)
    max_turns = agent.config.max_turns

    while agent.turn_count < max_turns:
        items = await ctx.repos.items.list_by_agent(agent.id)
        messages = _items_to_messages(items, agent.config.system_prompt)

        ctx.events.emit(Event(
            name="turn.start",
            agent_id=agent.id,
            data={"turn": agent.turn_count, "items": len(items)},
        ))

        estimated = estimate_tokens(messages, tool_defs or None)
        logger.info("Token estimate: ~%d tokens (turn %d)", estimated, agent.turn_count)

        logger.info("Sending messages: role=%s | content=%s", messages[-1].role, messages[-1].content)
        response = await ctx.provider.chat(
            model=agent.config.model,
            messages=messages,
            tools=tool_defs or None,
        )
        logger.info("Received response: finish_reason=%s | content=%s", response.finish_reason, response.content)

        if response.usage:
            logger.info(
                "Actual usage: in=%d out=%d total=%d cached=%s",
                response.usage.input_tokens, response.usage.output_tokens,
                response.usage.total_tokens, response.usage.cached_tokens,
            )

        # Store assistant text if present
        if response.content:
            await _store_item(
                ctx, agent.id,
                type=ItemType.MESSAGE,
                role="assistant",
                content=response.content,
            )

        # Store function calls
        for tc in response.tool_calls:
            await _store_item(
                ctx, agent.id,
                type=ItemType.FUNCTION_CALL,
                call_id=tc.id,
                name=tc.name,
                arguments=tc.arguments,
            )

        # Process tool calls
        human_waits: list[WaitEntry] = []
        for tc in response.tool_calls:
            tool = ctx.tools.get(tc.name)
            if tool is None:
                await _store_item(
                    ctx, agent.id,
                    type=ItemType.FUNCTION_CALL_OUTPUT,
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
                ))
                ctx.events.emit(Event(
                    name="tool.human_requested",
                    agent_id=agent.id,
                    data={"call_id": tc.id, "tool": tc.name, "arguments": tc.arguments},
                ))
            else:
                result = await ctx.tools.execute(tc.name, tc.arguments)
                await _store_item(
                    ctx, agent.id,
                    type=ItemType.FUNCTION_CALL_OUTPUT,
                    call_id=tc.id,
                    name=tc.name,
                    output=result.output,
                    is_error=result.is_error,
                )
                ctx.events.emit(Event(
                    name="tool.executed",
                    agent_id=agent.id,
                    data={"call_id": tc.id, "tool": tc.name, "is_error": result.is_error},
                ))

        if human_waits:
            agent = wait_for(agent, human_waits)
            await ctx.repos.agents.update(agent)
            ctx.events.emit(Event(
                name="agent.waiting",
                agent_id=agent.id,
                data={"waiting_for": [w.call_id for w in human_waits]},
            ))
            return agent

        agent.turn_count += 1
        await ctx.repos.agents.update(agent)

        # If no tool calls, we're done
        if not response.tool_calls:
            break

    agent = complete_agent(agent)
    await ctx.repos.agents.update(agent)
    ctx.events.emit(Event(name="agent.completed", agent_id=agent.id))
    return agent


async def deliver_result(ctx: RuntimeContext, agent: Agent, call_id: str, output: str) -> Agent:
    """Deliver a tool result to a waiting agent, then resume the loop."""
    await _store_item(
        ctx, agent.id,
        type=ItemType.FUNCTION_CALL_OUTPUT,
        call_id=call_id,
        output=output,
    )

    agent = deliver_one(agent, call_id)
    await ctx.repos.agents.update(agent)

    if agent.status == AgentStatus.RUNNING:
        ctx.events.emit(Event(name="agent.resumed", agent_id=agent.id))
        return await run_agent(ctx, agent)

    return agent
