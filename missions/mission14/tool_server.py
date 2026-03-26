"""Thin adapter — serves an HTTP endpoint that the external headquarters agent calls.

Accepts POST {"params": "natural language query"} and returns {"output": "..."}.
Internally runs the Erin agent to search CSV data in the shared workspace.
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

from src.entry import init_db, init_logging
from src.entry.standalone import StandaloneAgent

_MAX_OUTPUT_BYTES = 500
_MIN_OUTPUT_BYTES = 4
_AGENT_NAME = "erin"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_logging()
    await init_db()
    logger.info("Tool server ready — Erin agent loaded")
    yield


app = FastAPI(title="Mission 14 Tool Server", lifespan=lifespan)


@app.post("/api/search")
async def search_tool(request: Request) -> JSONResponse:
    """Endpoint called by the external headquarters agent."""
    body = await request.json()
    params = body.get("params", "")
    logger.info("Incoming query: {}", params)

    if not params or not params.strip():
        return JSONResponse({"output": "No query provided. Send a product name to search."})

    try:
        agent = StandaloneAgent(_AGENT_NAME)
        result = await agent.send(params)
        output = (result.output or "No results").strip()
    except (RuntimeError, ValueError, OSError) as exc:
        logger.error("Agent error: {}", exc)
        output = "Internal error — please retry."

    # Enforce byte limits
    encoded = output.encode("utf-8")
    if len(encoded) > _MAX_OUTPUT_BYTES:
        encoded = encoded[:_MAX_OUTPUT_BYTES]
        output = encoded.decode("utf-8", errors="ignore")
    if len(encoded) < _MIN_OUTPUT_BYTES:
        output = output.ljust(_MIN_OUTPUT_BYTES)

    logger.info("Response ({} bytes): {}", len(output.encode("utf-8")), output)
    return JSONResponse({"output": output})
