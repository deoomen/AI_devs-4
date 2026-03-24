"""Unified entry point for the AI agent app.

Usage:
    python main.py server                        # HTTP API server
    python main.py server --host 0.0.0.0 -p 3000 # custom host/port
    python main.py run "What is 2+2?"            # one-shot with default agent
    python main.py run -a bob "Hello"             # one-shot with specific agent
"""

import argparse
import asyncio
import sys

from src.domain.types import AgentStatus
from src.config import settings
from src.entry import init_db, init_logging
from loguru import logger

init_logging()


async def _run(agent_name: str, message: str) -> None:
    from src.entry.standalone import StandaloneAgent

    await init_db()
    agent = StandaloneAgent(agent_name)
    result = await agent.send(message)

    while result.status == AgentStatus.WAITING and result.waiting_for:
        for wait in result.waiting_for:
            logger.info("Agent asks: {}", result.output)
            answer = input(f"[{wait.tool_name}] Your answer: ")
            result = await agent.deliver(wait.call_id, answer)

    logger.info("Agent finished (status={}): {}", result.status, result.output)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Agent App")
    sub = parser.add_subparsers(dest="command")

    srv = sub.add_parser("server", help="Start the HTTP API server")
    srv.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    srv.add_argument("-p", "--port", type=int, default=8000, help="Port (default: 8000)")

    run_p = sub.add_parser("run", help="Run an agent standalone (one-shot)")
    run_p.add_argument("-a", "--agent", default=settings.agent_default_name,
                       help=f"Agent name (default: {settings.agent_default_name})")
    run_p.add_argument("message", help="User message to send")

    args = parser.parse_args()

    if args.command == "server":
        import uvicorn
        uvicorn.run("src.entry.server:app", host=args.host, port=args.port, reload=settings.debug)

    elif args.command == "run":
        asyncio.run(_run(args.agent, args.message))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
