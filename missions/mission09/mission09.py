from loguru import logger
import sys
from pathlib import Path

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

USER_MESSAGE = """\
Complete the "mailbox" mission. We have access to an operator's email inbox and need to extract three pieces of information.

## Context
We gained access to a System operator's mailbox. A resistance member named Wiktor sent a tip about our power plant operation from an anonymous proton.me address. We must search the mailbox and extract:

1. **date** — when (YYYY-MM-DD) the security department plans to attack our power plant
2. **password** — a password to the employee system still somewhere in the inbox
3. **confirmation_code** — confirmation code from a security department ticket (format: SEC- + 28 chars = 32 total)

## Known facts
- Wiktor sent his email from a `proton.me` domain
- The mailbox API supports Gmail-style operators: `from:`, `to:`, `subject:`, `OR`, `AND`
- The mailbox is ACTIVE — new messages may arrive while you work

## Strategy
1. Spawn charlie (email analyst agent) to search the mailbox
2. Charlie should start with `zmail help` to discover API actions, then search for emails
3. Key searches: emails from proton.me (Wiktor's tip), emails about passwords, emails from security department (SEC- codes)
4. Read full message contents — don't guess from subjects
5. Once you have all 3 values, submit to headquarters with task "mailbox" and answer: {"date": "YYYY-MM-DD", "password": "...", "confirmation_code": "SEC-..."}
6. If headquarters says values are wrong, spawn charlie again with the feedback to search for the correct values
7. The mailbox is live — if charlie can't find something, try again later as new messages may have arrived

## Rules
- Send answer to headquarters with task "mailbox" and answer: {"date": "...", "password": "...", "confirmation_code": "..."}
- Iterate based on headquarters feedback until you receive a flag
- Do NOT guess values — extract them from actual email contents

## First step
Think about your approach, then spawn charlie to start searching the mailbox.
"""


class Mission09(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "mailbox"

    async def run(self) -> None:
        from src.domain.types import AgentStatus
        from src.entry import init_db, init_logging
        from src.entry.standalone import StandaloneAgent

        init_logging()
        await init_db()

        agent = StandaloneAgent("alice")
        logger.info("Starting \"{}\" mission via agent (session={})", self.get_task_name(), agent.session_id)
        result = await agent.send(USER_MESSAGE)

        while result.status == AgentStatus.WAITING and result.waiting_for:
            for wait in result.waiting_for:
                logger.info("Agent asks: {}", result.output)
                answer = input(f"[{wait.tool_name}] Your answer: ")
                result = await agent.deliver(wait.call_id, answer)

        logger.info("Agent finished (status={}):\n{}", result.status, result.output)
