from loguru import logger
import sys
from pathlib import Path

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

USER_MESSAGE = """\
Complete the "goingthere" mission. Navigate a rocket through a 3×12 terrain grid to reach the base in Grudziądz.

## Mission context
A rocket travels east from column 1 (row 2) toward column 12 (target row given after start). The route is blocked by radar traps and rocks. Radio hints describe where each column's rock is. Radar traps must be disarmed before moving through them.

## Your task
Delegate the navigation to the **ivan** agent. Each ivan run does exactly one attempt:
1. Starts the game and plays move by move until success or first crash/shoot-down
2. On crash: writes failure details to `outbox/run_log.md`, writes `FAILED` to `outbox/result.md`, then stops
3. On success: writes the final game response to `outbox/result.md`
Ivan never restarts himself — **you** are the restart loop.

## After each ivan run
1. Read `outbox/result.md` from ivan's files in your inbox — check for a flag or success token
2. Read `outbox/run_log.md` — ivan writes a structured entry for every crash/shoot-down during his run. If the file does not exist, skip analysis and re-spawn ivan immediately with the base message
3. If result contains a flag (`{{FLG:...}}` or similar): submit to headquarters, task="goingthere"
4. If ivan failed (no flag, or result shows a crash): **analyze run_log.md with think**, then re-spawn ivan with an enhanced message (see below)
5. Iterate until you receive a confirmed flag

## How to enhance ivan's message on re-spawn
After reading `run_log.md`, use `think` to reason:
- What pattern of failures occurred? (e.g. repeated crashes at the same column, wrong hint interpretation, radar not disarmed)
- What specific rule or clarification would have prevented it?

Then re-spawn ivan with the **base delegation message below PLUS an appended "## Lessons from previous runs" section** summarising the hypotheses and concrete corrections for each failure. Be specific — not "be more careful" but "at col 5, hint 'on your port side' means rock at row-1, so the correct move was `right`, not `left`".

Accumulate lessons across all re-spawns (carry forward lessons from previous iterations into each new spawn).

## Base delegation message for ivan
---
Play the "goingthere" game at {{AIDEVS4_HEADQUARTERS_SYSTEM_URL}}. Navigate the rocket from start (col 1, row 2) to the target at col 12.

Game endpoint: POST {{AIDEVS4_HEADQUARTERS_SYSTEM_URL}}/verify
Body format: {"apikey": "{{AIDEVS4_HEADQUARTERS_API_KEY}}", "task": "goingthere", "answer": {"command": "<start|go|left|right>"}}

Frequency scanner: GET {{AIDEVS4_HEADQUARTERS_SYSTEM_URL}}/api/frequencyScanner?key={{AIDEVS4_HEADQUARTERS_API_KEY}}
Radio hints: POST {{AIDEVS4_HEADQUARTERS_SYSTEM_URL}}/api/getmessage  Body: {"apikey": "{{AIDEVS4_HEADQUARTERS_API_KEY}}"}
Disarm radar: POST {{AIDEVS4_HEADQUARTERS_SYSTEM_URL}}/api/frequencyScanner  Body: {"apikey": "{{AIDEVS4_HEADQUARTERS_API_KEY}}", "frequency": <n>, "disarmHash": "<SHA1(detectionCode+'disarm')>"}

Follow your full navigation procedure. Write the final game response verbatim to outbox/result.md. Always copy notes/run_log.md to outbox/run_log.md.
---

## Rules
- Do NOT try to play the game yourself — you lack http_request. Delegate 100% to ivan.
- Always read run_log.md after each ivan run, even if it succeeded — patterns there may prevent future failures.
- Never re-spawn ivan with the same message twice — always add or refine the lessons section.
- Iterate until you receive a flag.
"""


class Mission24(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "goingthere"

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
