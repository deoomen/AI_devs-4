from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.deps import check_rate_limit, get_runtime
from src.api.schemas import AgentResponse, ChatRequest, DeliverRequest
from src.domain.agent import Agent, AgentConfig
from src.domain.entry import Entry
from src.domain.ids import AgentId, EntryId
from src.domain.session import Session
from src.domain.types import AgentStatus, EntryType, Role
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
    ctx.user_id = user.id
    session = Session(id=ctx.session_id, user_id=user.id)
    await ctx.repos.sessions.create(session)

    # Create session workspace
    ws = SessionWorkspace(ctx.session_id)
    ws.setup()

    # Create agent
    agent_id = AgentId.generate()
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
    user_entry = Entry(
        id=EntryId.generate(),
        session_id=ctx.session_id,
        agent_id=agent.id,
        turn=0,
        sequence=0,
        type=EntryType.MESSAGE,
        role=Role.USER,
        content=req.input,
    )
    await ctx.repos.entries.create(user_entry)

    # Run agent
    try:
        agent = await run_agent(ctx, agent, user_input=req.input)
    except Exception as e:
        err = AppError(message=str(e), status_code=500, code=ErrorCode.AGENT_ERROR)
        return JSONResponse(status_code=500, content=error_envelope(err))

    entries = await ctx.repos.entries.list_by_agent(agent.id)
    last_text = _extract_last_assistant_text(entries)

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
    agent_id: AgentId,
    req: DeliverRequest,
    user=Depends(check_rate_limit),
    ctx: RuntimeContext = Depends(get_runtime),
):
    ctx.user_id = user.id
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

    entries = await ctx.repos.entries.list_by_agent(agent.id)
    last_text = _extract_last_assistant_text(entries)

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
    agent_id: AgentId,
    user=Depends(check_rate_limit),
    ctx: RuntimeContext = Depends(get_runtime),
):
    agent = await ctx.repos.agents.get(agent_id)
    if agent is None:
        err = AppError(message="Agent not found", status_code=404, code=ErrorCode.NOT_FOUND)
        return JSONResponse(status_code=404, content=error_envelope(err))

    entries = await ctx.repos.entries.list_by_agent(agent.id)
    last_text = _extract_last_assistant_text(entries)

    return AgentResponse(
        agent_id=agent.id,
        status=agent.status.value,
        output=last_text,
        waiting_for=[
            {"call_id": w.call_id, "tool_name": w.tool_name}
            for w in agent.waiting_for
        ] if agent.waiting_for else None,
    )


def _extract_last_assistant_text(entries: list[Entry]) -> str | None:
    for entry in reversed(entries):
        if entry.type == EntryType.MESSAGE and entry.role == Role.ASSISTANT and entry.content:
            return entry.content
    return None
