import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.deps import check_rate_limit, get_runtime
from src.api.schemas import AgentResponse, ChatRequest, DeliverRequest
from src.domain.agent import Agent, AgentConfig
from src.domain.item import Item
from src.domain.session import Session
from src.domain.types import AgentStatus, ItemType
from src.errors import AppError, ErrorCode, error_envelope
from src.runtime.context import RuntimeContext
from src.runtime.runner import deliver_result, run_agent
from src.workspace.loader import load_agent_config
from src.workspace.session import SessionWorkspace

router = APIRouter(prefix="/api/chat")


@router.post("/completions")
async def completions(
    req: ChatRequest,
    user=Depends(check_rate_limit),
    ctx: RuntimeContext = Depends(get_runtime),
):
    agent_config = load_agent_config(req.agent)
    if agent_config is None:
        err = AppError(message=f"Agent '{req.agent}' not found", status_code=404, code=ErrorCode.AGENT_NOT_FOUND)
        return JSONResponse(status_code=404, content=error_envelope(err))

    # Create session
    session = Session(id=ctx.session_id, user_id=user.id)
    await ctx.repos.sessions.create(session)

    # Create session workspace
    ws = SessionWorkspace(ctx.session_id)
    ws.setup()

    # Create agent
    agent_id = str(uuid.uuid4())
    agent_ws = ws.create_agent_dir(agent_id)
    agent = Agent(
        id=agent_id,
        session_id=session.id,
        status=AgentStatus.PENDING,
        config=agent_config,
        workspace_path=str(agent_ws),
    )
    await ctx.repos.agents.create(agent)
    ctx.agent_workspace = agent_ws

    # Store user message
    user_item = Item(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        sequence=0,
        type=ItemType.MESSAGE,
        role="user",
        content=req.input,
    )
    await ctx.repos.items.create(user_item)

    # Run agent
    try:
        agent = await run_agent(ctx, agent, user_id=user.id, user_input=req.input)
    except Exception as e:
        err = AppError(message=str(e), status_code=500, code=ErrorCode.AGENT_ERROR)
        return JSONResponse(status_code=500, content=error_envelope(err))

    items = await ctx.repos.items.list_by_agent(agent.id)
    last_text = _extract_last_assistant_text(items)

    if agent.status == AgentStatus.WAITING:
        return JSONResponse(
            status_code=202,
            content=AgentResponse(
                agent_id=agent.id,
                status=agent.status.value,
                output=last_text,
                waiting_for=[
                    {"call_id": w.call_id, "tool_name": w.tool_name}
                    for w in agent.waiting_for
                ],
            ).model_dump(),
        )

    return AgentResponse(
        agent_id=agent.id,
        status=agent.status.value,
        output=last_text,
    )


@router.post("/agents/{agent_id}/deliver")
async def deliver(
    agent_id: str,
    req: DeliverRequest,
    user=Depends(check_rate_limit),
    ctx: RuntimeContext = Depends(get_runtime),
):
    agent = await ctx.repos.agents.get(agent_id)
    if agent is None:
        err = AppError(message="Agent not found", status_code=404, code=ErrorCode.NOT_FOUND)
        return JSONResponse(status_code=404, content=error_envelope(err))

    if agent.status != AgentStatus.WAITING:
        err = AppError(message="Agent is not waiting for input", status_code=400, code=ErrorCode.NOT_WAITING)
        return JSONResponse(status_code=400, content=error_envelope(err))

    if agent.workspace_path:
        ctx.agent_workspace = Path(agent.workspace_path)

    try:
        agent = await deliver_result(ctx, agent, req.call_id, req.output)
    except Exception as e:
        err = AppError(message=str(e), status_code=500, code=ErrorCode.AGENT_ERROR)
        return JSONResponse(status_code=500, content=error_envelope(err))

    items = await ctx.repos.items.list_by_agent(agent.id)
    last_text = _extract_last_assistant_text(items)

    if agent.status == AgentStatus.WAITING:
        return JSONResponse(
            status_code=202,
            content=AgentResponse(
                agent_id=agent.id,
                status=agent.status.value,
                output=last_text,
                waiting_for=[
                    {"call_id": w.call_id, "tool_name": w.tool_name}
                    for w in agent.waiting_for
                ],
            ).model_dump(),
        )

    return AgentResponse(
        agent_id=agent.id,
        status=agent.status.value,
        output=last_text,
    )


@router.get("/agents/{agent_id}")
async def get_agent_status(
    agent_id: str,
    user=Depends(check_rate_limit),
    ctx: RuntimeContext = Depends(get_runtime),
):
    agent = await ctx.repos.agents.get(agent_id)
    if agent is None:
        err = AppError(message="Agent not found", status_code=404, code=ErrorCode.NOT_FOUND)
        return JSONResponse(status_code=404, content=error_envelope(err))

    items = await ctx.repos.items.list_by_agent(agent.id)
    last_text = _extract_last_assistant_text(items)

    return AgentResponse(
        agent_id=agent.id,
        status=agent.status.value,
        output=last_text,
        waiting_for=[
            {"call_id": w.call_id, "tool_name": w.tool_name}
            for w in agent.waiting_for
        ] if agent.waiting_for else None,
    )


def _extract_last_assistant_text(items: list[Item]) -> str | None:
    for item in reversed(items):
        if item.type == ItemType.MESSAGE and item.role == "assistant" and item.content:
            return item.content
    return None
