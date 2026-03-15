# Entry Points

## Current

### 1. HTTP (FastAPI)

- `src/main.py` -> `/api/chat/completions`, `/api/chat/agents/{id}/deliver`
- Request/response API. External systems call in, get a response back
- Supports async waiting via `/deliver` endpoint for `ask_user`-style tools

### 2. Standalone (Python API)

- `src/runtime/standalone.py` -> `StandaloneAgent`
- Programmatic Python API used by mission scripts
- Supports multi-turn, deliver/wait pattern, no server needed

Both share the same core: `RuntimeContext` + `run_agent()` from `runner.py`. Entry points only handle session/agent creation and I/O framing.

---

## Proposed

### 3. CLI REPL

Interactive terminal loop — `python -m app chat alice`. User types, agent responds, `ask_user` tool calls prompt via stdin.

**When useful:** day-to-day development, debugging agent behavior, quick one-off runs without spinning up the server. Tightest feedback loop for iterating on agents.

**Effort:** low — 30-40 lines wrapping `StandaloneAgent` with readline. Mission05 already does this ad-hoc with `input()`.

**Priority:** high — most immediate practical value.

### 4. Worker / Queue Consumer

Long-running process pulling tasks from a queue (Redis streams, SQS, RabbitMQ) and dispatching them to agents. Results go back to the queue or a callback URL.

**When useful:** decoupling caller from agent execution — batch processing, fan-out to multiple agents, retries with backoff, scaling workers independently from the API. Makes sense when external systems fire-and-forget tasks (e.g. AIDevs platform sending challenges, or a pipeline of missions).

**Effort:** medium — needs queue infra + a consumer loop around `StandaloneAgent`.

**Priority:** low — only when workload demands it.

### 5. WebSocket / SSE Streaming

Stream events as they happen — tool calls, intermediate text, waiting status — in real-time instead of blocking until the agent finishes all turns.

**When useful:** any frontend/UI showing the agent "thinking". Also useful for long-running agents where HTTP timeouts would kill the connection. The existing `EventEmitter` already produces the right events (`turn.start`, `tool.executed`, `agent.waiting`) — just pipe them to the socket.

**Effort:** medium — FastAPI supports WebSocket natively; main work is bridging `EventEmitter` to the socket.

**Priority:** medium — becomes important with a UI or long-running agents.

### 6. Scheduler / Cron Trigger

Time-based agent execution — "run agent X with message Y every hour" or "at 09:00 daily."

**When useful:** monitoring/reporting tasks, periodic data fetches, recurring missions.

**Effort:** low — thin wrapper around `StandaloneAgent` with APScheduler, cron, or systemd timer.

**Priority:** low — only when recurring tasks appear.

### 7. Webhook Receiver (Inbound Push)

Specialized HTTP endpoint accepting webhooks from external platforms (AIDevs, Slack, GitHub), translating payloads into agent messages and dispatching.

**When useful:** when external systems push events rather than you polling them. Different from the current HTTP API because the contract matches the external system's format, not your own schema. Mission03's `ProxyAgent` pattern is already close to this.

**Effort:** medium per integration — each external system has its own payload format/auth.

**Priority:** low — on-demand per integration.
