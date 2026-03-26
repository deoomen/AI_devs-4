"""Langfuse tracing provider.

Manages the Langfuse client singleton and wires agent lifecycle events
to Langfuse observations (SDK v4).

Tracing is disabled (no-op) when LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY
are not set or the ``langfuse`` package is not installed.
"""

from __future__ import annotations

from contextlib import ExitStack
from typing import TYPE_CHECKING

from loguru import logger

from src.config import settings
from src.events.emitter import EventEmitter
from src.events.types import Event, EventName

if TYPE_CHECKING:
    from langfuse import Langfuse


# ── Client management ─────────────────────────────────────────────────────────

_client: Langfuse | None = None


def _init_client() -> Langfuse | None:
    try:
        from langfuse import Langfuse  # noqa: PLC0415

        client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_base_url,
        )
        logger.info("Langfuse tracing enabled (base_url={})", settings.langfuse_base_url)
        return client
    except ImportError:
        logger.warning("langfuse package not installed — tracing disabled")
        return None
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Failed to initialize Langfuse: {}", exc)
        return None


def get_client() -> Langfuse | None:
    """Return the Langfuse client singleton, initializing on first call."""
    global _client  # pylint: disable=global-statement
    if _client is None:
        _client = _init_client()
    return _client


# ── Event listeners ───────────────────────────────────────────────────────────

def _str_meta(**kwargs) -> dict[str, str]:
    """Build metadata dict with only present non-None values, all cast to str (v4 requirement)."""
    return {k: str(v) for k, v in kwargs.items() if v is not None}


def attach_listeners(client: Langfuse, events: EventEmitter) -> None:
    """Wire Langfuse observation handlers to agent lifecycle events."""
    try:
        from langfuse import propagate_attributes  # noqa: PLC0415
    except ImportError:
        return

    # Root span refs — one per agent run, keyed by agent_id.
    _agent_spans: dict[str, object] = {}
    # ExitStacks holding the propagate_attributes context alive for each agent run.
    # Kept open so all child observations inherit user_id / session_id.
    _agent_stacks: dict[str, ExitStack] = {}

    # In-flight generation/tool observations.
    # Generation key: agent_id (sequential, one LLM call per turn).
    # Tool key: call_id (unique per tool invocation).
    _pending_gens: dict[str, object] = {}
    _pending_tools: dict[str, object] = {}

    # ── Agent lifecycle ────────────────────────────────────────────────────

    def on_agent_started(event: Event) -> None:
        d = event.data

        stack = ExitStack()
        stack.enter_context(propagate_attributes(
            user_id=d.get("user_id") or None,
            session_id=d.get("session_id") or None,
            trace_name=f"agent/{d.get('agent_name', 'agent')}",
        ))

        span = client.start_observation(
            as_type="span",
            name=f"agent/{d.get('agent_name', 'agent')}",
            input=d.get("user_input"),
            metadata=_str_meta(
                agent_name=d.get("agent_name"),
                model=d.get("model"),
            ),
        )
        _agent_spans[event.agent_id] = span
        _agent_stacks[event.agent_id] = stack

    def _close_agent(event: Event) -> object | None:
        stack = _agent_stacks.pop(event.agent_id, None)
        span = _agent_spans.pop(event.agent_id, None)
        if stack is not None:
            stack.close()
        return span

    def on_agent_completed(event: Event) -> None:
        span = _close_agent(event)
        if span is None:
            return
        span.update(output=event.data.get("output"), metadata={"status": "completed"})
        span.end()

    def on_agent_failed(event: Event) -> None:
        span = _close_agent(event)
        if span is None:
            return
        span.update(
            level="ERROR",
            metadata=_str_meta(status="failed", error=event.data.get("error")),
        )
        span.end()

    def on_agent_waiting(event: Event) -> None:
        # Don't close — agent may resume, span and propagate_attributes stay open
        span = _agent_spans.get(event.agent_id)
        if span is None:
            return
        waiting = ", ".join(str(w) for w in event.data.get("waiting_for", []))
        span.update(metadata=_str_meta(status="waiting", waiting_for=waiting))

    # ── Generation (LLM call) ──────────────────────────────────────────────

    def on_generation_started(event: Event) -> None:
        parent = _agent_spans.get(event.agent_id)
        if parent is None:
            return
        d = event.data
        gen = parent.start_observation(
            as_type="generation",
            name="llm",
            model=d.get("model") or None,
            input=d.get("input"),
        )
        _pending_gens[event.agent_id] = gen

    def on_generation_completed(event: Event) -> None:
        gen = _pending_gens.pop(event.agent_id, None)
        if gen is None:
            return
        d = event.data
        usage = d.get("usage")
        gen.update(
            model=d.get("model"),
            output=d.get("output") or "",
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

    # ── Tool execution ─────────────────────────────────────────────────────

    def on_tool_started(event: Event) -> None:
        parent = _agent_spans.get(event.agent_id)
        if parent is None:
            return
        d = event.data
        span = parent.start_observation(
            as_type="tool",
            name=d["name"],
            input=d.get("arguments"),
        )
        _pending_tools[d["call_id"]] = span

    def on_tool_completed(event: Event) -> None:
        d = event.data
        span = _pending_tools.pop(d["call_id"], None)
        if span is None:
            return
        is_error = d.get("is_error", False)
        span.update(
            output=d.get("output"),
            level="ERROR" if is_error else "DEFAULT",
            metadata=_str_meta(is_error=is_error),
        )
        span.end()

    events.on(EventName.AGENT_STARTED, on_agent_started)
    events.on(EventName.AGENT_COMPLETED, on_agent_completed)
    events.on(EventName.AGENT_FAILED, on_agent_failed)
    events.on(EventName.AGENT_WAITING, on_agent_waiting)
    events.on(EventName.GENERATION_STARTED, on_generation_started)
    events.on(EventName.GENERATION_COMPLETED, on_generation_completed)
    events.on(EventName.TOOL_STARTED, on_tool_started)
    events.on(EventName.TOOL_COMPLETED, on_tool_completed)
