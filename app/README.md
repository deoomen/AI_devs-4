# AI Agent App

Async Python AI agent framework with tool-calling, human-in-the-loop, and persistent state. Built on FastAPI + SQLAlchemy + OpenRouter (OpenAI-compatible).

Agents are defined as markdown files with YAML frontmatter. They run in a loop — calling the LLM, executing tools, storing results — until done or paused for human input.

## Project Structure

```
app/
├── alembic/                  # Database migrations (Alembic, async SQLite)
├── docs/                     # Feature requests and design docs
├── src/                      # Application source code
│   ├── api/                  # HTTP layer (schemas, dependency injection)
│   │   └── routes/           # FastAPI route handlers (chat, health)
│   ├── db/                   # Async SQLAlchemy engine, ORM models, seeding
│   ├── domain/               # Core entities (Agent, Session, Item, User) and enums
│   ├── events/               # Pub/sub event emitter and handlers
│   ├── middleware/            # Auth (Bearer token) and per-user rate limiting
│   ├── providers/            # LLM provider abstraction (OpenRouter / OpenAI-compatible)
│   ├── repositories/         # Data access layer (CRUD for each entity)
│   ├── runtime/              # Agent execution loop, standalone runner, template engine
│   ├── tools/                # Tool registry, definitions, path safety
│   │   └── native/           # Built-in tools (http_request, read/write_file, csv_filter, etc.)
│   └── workspace/            # Agent config loader (YAML frontmatter .agent.md files)
└── workspace/                # Runtime data (agent definitions, sandbox files)
    └── agents/               # Agent definitions (YAML frontmatter + system prompt)
```

## Setup

```bash
# 1. Create .env from example
cp app/.env.example app/.env

# 2. Fill in required values
#    - openrouter_api_key   (required — LLM provider)
#    - api_key              (optional — default auth token)

# 3. Install dependencies
pip install -r requirements.txt

# 4. Tables are created automatically on first startup
```

## Running

### API Server

```bash
# From project root
cd app
python -m src.main

# Or with uvicorn directly
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Standalone Runtime (no HTTP server)

```python
import asyncio
from src.runtime.standalone import StandaloneAgent

async def main():
    agent = StandaloneAgent("alice")
    result = await agent.send("What is 2 + 2?")
    print(result.output)

    # Multi-turn: send follow-up to the same agent
    result = await agent.send("Now multiply that by 10")
    print(result.output)

asyncio.run(main())
```

If the agent calls `ask_user` (human-in-the-loop), it pauses and returns `status=WAITING`:

```python
async def interactive():
    agent = StandaloneAgent("alice")
    result = await agent.send("Ask me something first")

    if result.status.value == "waiting":
        wait = result.waiting_for[0]
        print(f"Agent asks: {result.output}")
        answer = input("> ")
        result = await agent.deliver(wait.call_id, answer)

    print(result.output)
```

One-shot convenience:

```python
from src.runtime.standalone import run_agent_standalone

output = await run_agent_standalone("alice", "Hello!")
```

## API Endpoints

All chat endpoints require `Authorization: Bearer <api_key>` header.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check → `{"status": "ok"}` |
| `POST` | `/api/chat/completions` | Create and run an agent |
| `POST` | `/api/chat/agents/{agent_id}/deliver` | Resume a waiting agent with tool result |
| `GET` | `/api/chat/agents/{agent_id}` | Poll agent status |

### POST /api/chat/completions

```json
{
  "agent": "alice",
  "input": "Your message here"
}
```

Returns `200` with `AgentResponse` if completed, `202` if agent is waiting for human input.

### POST /api/chat/agents/{agent_id}/deliver

```json
{
  "call_id": "uuid-from-waiting_for",
  "output": "User's answer"
}
```

### AgentResponse

```json
{
  "agent_id": "uuid",
  "status": "completed",
  "output": "Agent's last message",
  "waiting_for": [
    {"call_id": "uuid", "tool_name": "ask_user"}
  ]
}
```

Status values: `pending`, `running`, `waiting`, `completed`, `failed`.

## Adding a New Tool

### 1. Create the tool file

`src/tools/native/my_tool.py`:

```python
from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult

async def _execute(arguments: dict) -> ToolResult:
    value = arguments["param"]
    # ... your logic ...
    return ToolResult(output=f"Result: {value}")

my_tool = Tool(
    name="my_tool",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="my_tool",
        description="What the LLM sees when choosing tools",
        parameters={
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "Description for LLM"},
            },
            "required": ["param"],
        },
    ),
    execute=_execute,
)
```

Tool types:
- `SYNC` — executed immediately by the agent loop
- `HUMAN` — pauses agent, waits for external input via `/deliver`

### 2. Register in the registry

In `src/tools/registry.py`, add to `build_default()`:

```python
from .native.my_tool import my_tool

registry.register(my_tool)
```

### 3. Enable on an agent

Add the tool name to the agent's `tools` list in its `.agent.md` file.

## Adding a New Agent

Create `workspace/agents/myagent.agent.md`:

```yaml
---
name: myagent
model: ""
tools:
  - http_request
  - read_file
  - write_file
max_turns: 10
---
You are MyAgent. Describe personality and instructions here.

This markdown body becomes the system prompt.
```

- `model: ""` uses the default from `openrouter_default_model` setting
- `tools` lists which registered tools the agent can call
- `max_turns` limits the LLM call loop iterations

Use the agent:

```bash
# API
curl -X POST http://localhost:8000/api/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent": "myagent", "input": "Hello"}'
```

```python
# Standalone
agent = StandaloneAgent("myagent")
result = await agent.send("Hello")
```

## Configuration

Key settings in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `debug` | `false` | Enable debug logging |
| `api_key` | `change-me` | Bearer token for API auth |
| `database_url` | `sqlite+aiosqlite:///./agent.db` | Database connection string |
| `openrouter_api_key` | — | OpenRouter API key (required) |
| `openrouter_default_model` | `openai/gpt-4.1-mini` | Default LLM model |
| `agent_workspace_dir` | `workspace/sandbox` | Sandboxed file workspace |
| `agent_rate_limit_rpm` | `30` | Max requests per minute per user |
| `agent_max_turns` | `10` | Default max LLM loop iterations |
