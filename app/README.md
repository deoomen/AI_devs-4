# AI Agent App

Async Python AI agent framework with tool-calling, human-in-the-loop, and persistent state. Built on FastAPI + SQLAlchemy + OpenRouter (OpenAI-compatible).

Agents are defined as markdown files with YAML frontmatter. They run in a loop — calling the LLM, executing tools, storing results — until done or paused for human input.

## Project Structure

```
app/                    # Root directory
├── alembic/            # Database migrations (Alembic, async SQLite)
├── src/                # Application source code
│   ├── api/            # HTTP layer (schemas, dependency injection)
│   │   └── routes/     # FastAPI route handlers (chat, health)
│   ├── db/             # Async SQLAlchemy engine, ORM models, seeding
│   ├── domain/         # Core entities (Agent, Session, Entry, User) and enums
│   ├── entry/          # Entry points (HTTP server, standalone runner)
│   ├── events/         # Pub/sub event emitter, handlers, event types
│   ├── middleware/     # Auth (Bearer token) and per-user rate limiting
│   ├── providers/      # LLM provider abstraction (OpenRouter / OpenAI-compatible)
│   ├── repositories/   # Data access layer (CRUD for each entity)
│   ├── runtime/        # Agent execution loop, runtime context
│   ├── tools/          # Tool registry, template resolution, workspace path safety
│   │   └── native/     # Built-in tools (see Available Tools below)
│   ├── workspace/      # Agent config loader and session workspace management
│   │   └── agents/     # Agent definitions (YAML frontmatter + system prompt)
│   ├── workspace/      # Runtime data (date-based session directories)
│   ├── config.py       # Pydantic settings (loads .env)
│   ├── errors.py       # Application error types
│   └── log.py          # Logging setup (loguru)
└main.py                # CLI entry point (server, run agent one-shot)
```

## Available Tools

| Tool | Description |
|------|-------------|
| `aidevs_headquarters` | Send reports to AIDevs headquarters API |
| `ask_user` | Human-in-the-loop — pauses agent, waits for user input |
| `csv_filter` | Filter and query CSV files |
| `download_file` | Download files from URLs |
| `http_request` | Make HTTP requests (GET, POST, etc.) |
| `list_files` | List files in the agent workspace |
| `read_file` | Read file contents from the agent workspace |
| `write_file` | Write files to the agent workspace |

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

All commands from the `app/` directory:

```bash
cd app

# Start the HTTP API server (default: 0.0.0.0:8000)
python main.py server
python main.py server --host 127.0.0.1 -p 3000

# Run an agent one-shot (uses default agent from settings)
python main.py run "What is 2 + 2?"
python main.py run -a bob "Hello"
```

If the agent calls `ask_user`, the CLI will prompt for input interactively.

### Programmatic Usage

```python
import asyncio
from src.domain.types import AgentStatus
from src.entry import init_db, init_logging
from src.entry.standalone import StandaloneAgent
from loguru import logger

async def main():
    init_logging()
    await init_db()

    agent = StandaloneAgent("alice")
    
    # Single-turn:
    result = await agent.send("What is 2 + 2?")
    logger.info("Agent response (status={}): {}", result.status, result.output)

    # Multi-turn: send follow-up to the same agent
    result = await agent.send("Now multiply that by 10")

    while result.status == AgentStatus.WAITING and result.waiting_for:
        for wait in result.waiting_for:
            logger.info("Agent asks: {}", result.output)
            answer = input(f"[{wait.tool_name}] Your answer: ")
            result = await agent.deliver(wait.call_id, answer)
    else:
        logger.info("Agent finished (status={}): {}", result.status, result.output)

asyncio.run(main())
```

## API Endpoints

All chat endpoints require `Authorization: Bearer <api_key>` header.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
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

Create `src/workspace/agents/myagent.agent.md`:

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

- `model: ""` uses the default from `openrouter_default_chat_model` setting
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

## Template Variables

Tool arguments support `{{PLACEHOLDER}}` syntax. Variables are resolved at execution time (never stored in DB or sent to LLM). Only whitelisted variables are resolved — configured via `template_whitelist` in settings.

## Workspace & File Access

Agents operate in isolated, session-scoped workspaces. File tools enforce directory-level access control:

- **Write**: `notes/`, `outbox/` only
- **Read**: `inbox/`, `notes/`, `outbox/` only

This prevents agents from escaping their workspace or accessing other agents' data.

## Configuration

Key settings in `.env`:

| Variable                          | Default                          | Description                             |
|-----------------------------------|----------------------------------|-----------------------------------------|
| `debug`                           | `false`                          | Enable debug logging                    |
| `log_level`                       | `INFO`                           | Log level (DEBUG, INFO, WARNING, ERROR) |
| `api_key`                         | `change-me`                      | Bearer token for API auth               |
| `database_url`                    | `sqlite+aiosqlite:///./agent.db` | Database connection string              |
| `openrouter_api_key`              | —                                | OpenRouter API key (required)           |
| `openrouter_default_chat_model`   | `openai/gpt-4.1-mini`            | Default LLM chat model                  |
| `openrouter_default_vision_model` | `google/gemini-3-flash-preview`  | Default vision model                    |
| `provider_max_retries`            | `3`                              | Max retries for LLM provider calls      |
| `aidevs4_headquarters_api_key`    | —                                | AIDevs headquarters API key             |
| `aidevs4_headquarters_url`        | -                                | AIDevs headquarters URL                 |
| `agent_default_name`              | `alice`                          | Default agent when none specified       |
| `agent_workspace_dir`             | `workspace`                      | Runtime workspace directory             |
| `agent_rate_limit_rpm`            | `30`                             | Max requests per minute per user        |
| `agent_max_turns`                 | `10`                             | Default max LLM loop iterations         |
