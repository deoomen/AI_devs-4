"""Langfuse event subscriber.

Subscribes to agent events and creates Langfuse observations.
Stateful only for agent traces (need to track refs for nesting and lifecycle).
Generations and tool spans are fire-and-forget — their events carry all needed data.

Mirrors the TypeScript `langfuse-subscriber.ts` pattern from 01_05_agent.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from loguru import logger

from src.events.emitter import EventEmitter
from src.events.types import Event, EventName
from src.tracing.langfuse import get_langfuse

if TYPE_CHECKING:
    from langfuse.client import StatefulTraceClient


def _ts(unix: float) -> datetime:
    return datetime.fromtimestamp(unix, tz=timezone.utc)


def subscribe_langfuse(events: EventEmitter) -> None:
    """Attach Langfuse listeners to the event emitter. No-op when tracing is off."""
    client = get_langfuse()
    if client is None:
        return

    # Agent trace refs — keyed by agent_id, needed for nesting child observations
    _traces: dict[str, "StatefulTraceClient"] = {}

    # ── Agent lifecycle ───────────────────────────────────────────────────────

    def on_agent_started(event: Event) -> None:
        d = event.data
        trace = client.trace(
            id=event.agent_id,
            name=f"agent/{d.get('agent_name', 'agent')}",
            session_id=d.get("session_id"),
            user_id=d.get("user_id") or None,
            input=d.get("user_input"),
            metadata={
                "agent_name": d.get("agent_name"),
                "model": d.get("model"),
            },
        )
        _traces[event.agent_id] = trace

    def on_agent_completed(event: Event) -> None:
        trace = _traces.pop(event.agent_id, None)
        if trace is None:
            return
        trace.update(output=event.data.get("output"), metadata={"status": "completed"})

    def on_agent_failed(event: Event) -> None:
        trace = _traces.pop(event.agent_id, None)
        if trace is None:
            return
        trace.update(metadata={"status": "failed", "error": event.data.get("error")})

    def on_agent_waiting(event: Event) -> None:
        # Don't pop — agent may resume, trace stays open
        trace = _traces.get(event.agent_id)
        if trace is None:
            return
        waiting = ", ".join(str(w) for w in event.data.get("waiting_for", []))
        trace.update(output=f"Waiting for: {waiting}", metadata={"status": "waiting"})

    # ── Generation (LLM call) ─────────────────────────────────────────────────

    def on_generation_completed(event: Event) -> None:
        trace = _traces.get(event.agent_id)
        if trace is None:
            return
        d = event.data
        start = _ts(d["start_time"])
        end = _ts(d["start_time"] + d["duration_ms"] / 1000)
        usage = d.get("usage")

        gen = trace.generation(
            name="llm",
            model=d.get("model"),
            input=d.get("input"),
            start_time=start,
            metadata={"turn": d.get("turn"), "finish_reason": d.get("finish_reason")},
        )
        gen.end(
            output=d.get("output") or "",
            end_time=end,
            usage={
                "input": usage["input_tokens"],
                "output": usage["output_tokens"],
                "total": usage["total_tokens"],
            } if usage else None,
        )

    # ── Tool execution ────────────────────────────────────────────────────────

    def on_tool_completed(event: Event) -> None:
        trace = _traces.get(event.agent_id)
        if trace is None:
            return
        d = event.data
        start = _ts(d["start_time"])
        end = _ts(d["start_time"] + d["duration_ms"] / 1000)
        is_error = d.get("is_error", False)

        span = trace.span(
            name=f"tool/{d['name']}",
            input=d.get("arguments"),
            start_time=start,
        )
        span.end(
            output=d.get("output"),
            end_time=end,
            level="ERROR" if is_error else "DEFAULT",
            metadata={"is_error": is_error},
        )

    events.on(EventName.AGENT_STARTED, on_agent_started)
    events.on(EventName.AGENT_COMPLETED, on_agent_completed)
    events.on(EventName.AGENT_FAILED, on_agent_failed)
    events.on(EventName.AGENT_WAITING, on_agent_waiting)
    events.on(EventName.GENERATION_COMPLETED, on_generation_completed)
    events.on(EventName.TOOL_COMPLETED, on_tool_completed)

    logger.info("Langfuse subscriber attached")
