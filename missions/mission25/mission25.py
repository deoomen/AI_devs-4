import sys
from loguru import logger
from pathlib import Path

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

_JUMP_MESSAGES = {
    1: """\
Execute the timetravel mission autonomously. Configure the CHRONOS-P1 device and complete all three jumps:

1. Jump to 5 November 2238 — collect replacement batteries
2. Return to today (2026-04-10)
3. Open a time tunnel to 12 November 2024 — meet Rafał

Start with Phase 0 (reset device, fetch docs, read PWR table) then execute all three jumps without stopping.
""",
    2: """\
Resume the timetravel mission. Jump 1 (→ 2238-11-05) is already complete. The device is back in standby.

Execute the remaining two jumps without stopping:
2. Return to today (2026-04-10) — past jump, PT-A on, PT-B off
3. Open a time tunnel to 12 November 2024 — past tunnel, PT-A on, PT-B on

Skip Phase 0 setup (docs already fetched). Start directly with Jump 2 per-jump procedure.
Do NOT reset the device — batteries were already collected in Jump 1.
""",
    3: """\
Resume the timetravel mission. Jumps 1 and 2 are already complete. The device is back in standby at today's date (2026-04-10).

Execute the final jump without stopping:
3. Open a time tunnel to 12 November 2024 — past tunnel, PT-A on, PT-B on

Skip Phase 0 setup. Start directly with Jump 3 per-jump procedure.
Do NOT reset the device.
""",
}


class Mission25(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "timetravel"

    async def run(self) -> None:
        from src.domain.types import AgentStatus
        from src.entry import init_db, init_logging
        from src.entry.standalone import StandaloneAgent

        # Optional: python main.py 25 2  → start from jump 2
        start_jump = 1
        if len(sys.argv) > 2:
            try:
                start_jump = int(sys.argv[2])
                if start_jump not in _JUMP_MESSAGES:
                    raise ValueError
            except ValueError:
                logger.error("Invalid jump number '{}'. Use 1, 2, or 3.", sys.argv[2])
                return

        user_message = _JUMP_MESSAGES[start_jump]
        logger.info("Starting \"{}\" mission from jump {}", self.get_task_name(), start_jump)

        init_logging()
        await init_db()

        agent = StandaloneAgent("judy")
        logger.info("Session: {}", agent.session_id)
        result = await agent.send(user_message)

        while result.status == AgentStatus.WAITING and result.waiting_for:
            for wait in result.waiting_for:
                logger.info("Agent asks: {}", result.output)
                answer = input(f"[{wait.tool_name}] Your answer: ")
                result = await agent.deliver(wait.call_id, answer)

        logger.info("Agent finished (status={}):\n{}", result.status, result.output)
