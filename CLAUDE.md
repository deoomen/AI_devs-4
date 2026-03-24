# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python 3.14 project with two systems:
1. **Mission system** (root `main.py`) — standalone scripts for AI_devs 4 course assignments
2. **Agent framework** (`app/`) — async FastAPI app with tool-calling agents, human-in-the-loop, and persistent state

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run missions (from project root)
python main.py 01          # run mission 01

# Run agent framework (from app/ directory)
cd app
python main.py server                          # HTTP API on 0.0.0.0:8000
python main.py server --host 127.0.0.1 -p 3000
python main.py run "message"                   # one-shot, default agent (alice)
python main.py run -a bob "message"            # one-shot, specific agent

# Lint (from project root)
.venv/bin/pylint app/ services/ missions/ config.py main.py

# Enable git pre-push hook (pylint errors+fatal)
git config core.hooksPath .githooks
```

No test suite exists yet. Pylint is the only automated quality check.

## Architecture

### Mission System (Legacy)
- `main.py` dynamically imports `missions.missionNN.missionNN.MissionNN` and calls `.run()`
- Each mission inherits `missions.base_mission.BaseMission` (ABC with async `run()`)
- Shared services: `services/OpenRouter.py`, `services/AIdevs4.py`, `services/Logging.py`
- Config: `config.py` loads from root `.env`

### Agent Framework (`app/`)
Entry: `app/main.py` → subcommands `server` (uvicorn) or `run` (standalone)

**Agent execution loop** (`src/runtime/runner.py`):
1. Load agent config from `src/workspace/agents/{name}.agent.md` (YAML frontmatter + markdown system prompt)
2. Call LLM with system prompt + conversation history
3. Execute tool calls — `SYNC` tools run immediately, `HUMAN` tools (e.g. `ask_user`) pause the agent
4. Store all entries (messages, tool calls, outputs) to SQLite
5. Loop until agent completes, fails, or hits `max_turns`

**Key layers:**
- `src/domain/` — entities (`Agent`, `Session`, `Entry`, `User`), typed ID value objects (`AgentId`, `SessionId`, etc.), enums
- `src/runtime/` — agent loop (`runner.py`), runtime context
- `src/tools/` — tool registry (`registry.py`), 14 built-in tools in `native/`, template variable resolution (`{{PLACEHOLDER}}`)
- `src/providers/` — LLM abstraction; OpenRouter (OpenAI-compatible) with retries
- `src/workspace/` — agent config loader, session workspace (date-based dirs with access control)
- `src/api/` — FastAPI routes, schemas, dependency injection (auth, rate limit)
- `src/db/` — async SQLAlchemy + aiosqlite, ORM models
- `src/events/` — pub/sub event emitter for agent lifecycle events
- `src/entry/` — `server.py` (FastAPI app), `standalone.py` (programmatic usage)

**Workspace isolation:** Each agent gets a scoped directory under `workspace/YYYY/MM/DD/ses_{id}/agents/agnt_{id}/` with `inbox/`, `notes/`, `outbox/` subdirs. File tools enforce read/write boundaries. Subagents communicate via file bridging (parent outbox → child inbox).

**Adding tools:** Create `src/tools/native/my_tool.py` with a `Tool` object, register in `registry.py:build_default()`, add to agent's `tools` list in its `.agent.md`.

**Adding agents:** Create `src/workspace/agents/name.agent.md` with YAML frontmatter (`name`, `model`, `tools`, `max_turns`) and markdown body (becomes system prompt).

## Configuration

- App settings: `app/.env` (Pydantic `BaseSettings` in `src/config.py`)
- Mission settings: root `.env`
- Required: `openrouter_api_key`
- LLM provider: OpenRouter (`openrouter_default_chat_model`, `openrouter_default_vision_model`)
- Database: SQLite async, auto-created on first run (`agent.db`)

## Lint Configuration

Pylint config in `pyproject.toml`:
- Currently enforcing: Errors (E), Fatal (F), Warnings (W)
- Max line length: 120
- Ignored dirs: `alembic`, `__pycache__`
- Pre-push hook fails on E/F only (`fail-on = "E,F"`)

## Conventions

- Commit messages use conventional format: `feat:`, `fix:`, `refactor:`, `chore:`, `docs:`
- Typed ID value objects (`AgentId`, `SessionId`, etc.) instead of plain strings/UUIDs
- Async-first: asyncio throughout (SQLAlchemy async, httpx, uvicorn)
- Agent definitions are markdown files with YAML frontmatter, not Python classes
