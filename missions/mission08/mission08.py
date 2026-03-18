from loguru import logger
import sys
from pathlib import Path

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

USER_MESSAGE = """\
Complete the "failure" mission. Yesterday there was a power plant failure. You have access to a full system log file from that day — but it's huge.

## Context
Your goal: prepare a condensed version of the logs (max 1500 tokens) containing only events relevant to analyzing the failure (power, cooling, water pumps, software, and other plant subsystems), then send it to headquarters and iterate based on feedback until you get a flag. 
A full system log file is available at:
{{AIDEVS4_HEADQUARTERS_SYSTEM_URL}}/data/{{AIDEVS4_HEADQUARTERS_API_KEY}}/failure.log - don't care about placeholders. It will be swapped in runtime when the agent receives the message.

The log file is very large — it won't fit in a single context window so you will need to read them in chunks. Filter by severity, each severity save as separate file.

## Goal
Prepare a condensed version of the logs containing only events relevant to analyzing the failure, then send it to headquarters and iterate based on their feedback until you receive a flag.

## Rules
- Send answer to headquarters with task "failure" and answer: {"logs": "<lines joined with \\n>"}
- Each line = one event with: date (YYYY-MM-DD), time (HH:MM), severity level, and component ID
- You may shorten/paraphrase event descriptions but must preserve timestamps, severity, and component IDs
- HARD LIMIT: 1500 tokens for the logs field. Always verify before sending.
- Start with fewer, most critical entries rather than trying to include everything at once. Iterate based on feedback.
- When iterating, pass the headquarters feedback AND your current logs to the research agent so he knows what to look for.
- Save each action to separate file.

## First step
Before doing anything, take a moment to think and prepare a step-by-step plan for completing this mission. Then execute your plan.
"""


class Mission08(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "failure"

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
