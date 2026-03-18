"""Langfuse event subscriber (SDK v4).

Subscribes to agent events and creates Langfuse observations using the v4
manual start_observation() API (no context-manager required).

Stateful only for root span refs (needed for nesting child observations and
agent lifecycle management). Generations and tool spans are fire-and-forget —
their events carry all the data needed to open and close them in one handler.

Mirrors the TypeScript `langfuse-subscriber.ts` pattern from 01_05_agent.
"""

from datetime import datetime, timezone

from loguru import logger

from src.events.emitter import EventEmitter
from src.events.types import Event, EventName
from src.tracing.langfuse import get_langfuse


def _ts(unix: float) -> datetime:
    return datetime.fromtimestamp(unix, tz=timezone.utc)


def _str_meta(**kwargs) -> dict[str, str]:
    """Build a metadata dict with only present values, all cast to str (v4 requirement)."""
    return {k: str(v) for k, v in kwargs.items() if v is not None}


def subscribe_langfuse(events: EventEmitter) -> None:
    """Attach Langfuse listeners to the event emitter. No-op when tracing is off."""
    client = get_langfuse()
    if client is None:
        return

    # Root span refs — one per agent run, keyed by agent_id.
    # Held open until agent.completed / agent.failed so generations and tool
    # spans can be nested under them via parent.start_observation().
    _spans: dict[str, object] = {}

    # ── Agent lifecycle ───────────────────────────────────────────────────────

    def on_agent_started(event: Event) -> None:
        d = event.data
        span = client.start_observation(
            as_type="span",
            name=f"agent/{d.get('agent_name', 'agent')}",
            input=d.get("user_input"),
            metadata=_str_meta(
                agent_name=d.get("agent_name"),
                model=d.get("model"),
                session_id=d.get("session_id"),
                user_id=d.get("user_id"),
            ),
        )
        _spans[event.agent_id] = span

    def on_agent_completed(event: Event) -> None:
        span = _spans.pop(event.agent_id, None)
        if span is None:
            return
        span.update(output=event.data.get("output"), metadata={"status": "completed"})
        span.end()

    def on_agent_failed(event: Event) -> None:
        span = _spans.pop(event.agent_id, None)
        if span is None:
            return
        span.update(
            level="ERROR",
            metadata=_str_meta(status="failed", error=event.data.get("error")),
        )
        span.end()

    def on_agent_waiting(event: Event) -> None:
        # Don't pop/end — agent may resume, span stays open
        span = _spans.get(event.agent_id)
        if span is None:
            return
        waiting = ", ".join(str(w) for w in event.data.get("waiting_for", []))
        span.update(metadata=_str_meta(status="waiting", waiting_for=waiting))

    # ── Generation (LLM call) ─────────────────────────────────────────────────

    def on_generation_completed(event: Event) -> None:
        parent = _spans.get(event.agent_id)
        if parent is None:
            return
        d = event.data
        usage = d.get("usage")

        gen = parent.start_observation(
            as_type="generation",
            name="llm",
            model=d.get("model"),
            input=d.get("input"),
            start_time=_ts(d["start_time"]),
        )
        gen.update(
            output=d.get("output") or "",
            end_time=_ts(d["start_time"] + d["duration_ms"] / 1000),
            usage_details={
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
                "total_tokens": usage["total_tokens"],
            } if usage else None,
            metadata=_str_meta(
                turn=d.get("turn"),
                finish_reason=d.get("finish_reason"),
            ),
        )
        gen.end()

    # ── Tool execution ────────────────────────────────────────────────────────

    def on_tool_completed(event: Event) -> None:
        parent = _spans.get(event.agent_id)
        if parent is None:
            return
        d = event.data
        is_error = d.get("is_error", False)

        span = parent.start_observation(
            as_type="span",
            name=f"tool/{d['name']}",
            input=d.get("arguments"),
            start_time=_ts(d["start_time"]),
        )
        span.update(
            output=d.get("output"),
            end_time=_ts(d["start_time"] + d["duration_ms"] / 1000),
            level="ERROR" if is_error else "DEFAULT",
            metadata=_str_meta(is_error=is_error),
        )
        span.end()

    events.on(EventName.AGENT_STARTED, on_agent_started)
    events.on(EventName.AGENT_COMPLETED, on_agent_completed)
    events.on(EventName.AGENT_FAILED, on_agent_failed)
    events.on(EventName.AGENT_WAITING, on_agent_waiting)
    events.on(EventName.GENERATION_COMPLETED, on_generation_completed)
    events.on(EventName.TOOL_COMPLETED, on_tool_completed)

    logger.info("Langfuse subscriber attached")
