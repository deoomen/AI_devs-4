from loguru import logger
import sys
from pathlib import Path

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

USER_MESSAGE = """\
Complete the "drone" mission. We've taken control of an armed drone and need to bomb a dam near the Żarnowiec power plant.

## Context
The System's Security Department plans to destroy our power plant. We'll make a preemptive strike: send the drone to bomb the **dam** (NOT the power plant) to restore water flow to the cooling system. The automated system will mark the target as destroyed, buying us time.

Plant ID: PWR6132PL

## Available resources
- **Terrain map** (PNG image with grid): {{AIDEVS4_HEADQUARTERS_SYSTEM_URL}}/data/{{AIDEVS4_HEADQUARTERS_API_KEY}}/drone.png
  - Divided into sectors by a grid. Dam area has intensified water color.
  - Rows and columns are 1-indexed.
- **Drone API documentation** (HTML): {{AIDEVS4_HEADQUARTERS_SYSTEM_URL}}/dane/drone.html
  - WARNING: The docs contain many conflicting function names — traps. Focus only on what's needed for the mission.

## Strategy

### Phase 1 — Gather intelligence (spawn both agents in parallel)

1. **Spawn dave** (image analyst) with this task:
   - Analyze the map image at this URL: {{AIDEVS4_HEADQUARTERS_SYSTEM_URL}}/data/{{AIDEVS4_HEADQUARTERS_API_KEY}}/drone.png
   - The map is divided into a grid of sectors (rows and columns).
   - Count the exact number of rows and columns in the grid.
   - Locate the dam — look for an area with intensified blue/water color near the edge of the map.
   - Report the dam's sector as (row, column), both 1-indexed.
   - Write findings to outbox/ file.

2. **Spawn bob** (researcher) with this task:
   - Download the drone API documentation from {{AIDEVS4_HEADQUARTERS_SYSTEM_URL}}/dane/drone.html
   - Read and analyze the HTML documentation.
   - Identify which API functions/instructions are needed to: configure the drone, set a target sector, and launch the mission.
   - The docs are full of traps — many conflicting function names. Focus only on what's essential for a bombing mission.
   - Write a concise summary of the needed instructions to outbox/ file.

### Phase 2 — Reason and execute

3. Read results from both agents (check inbox/ for their output files).
4. Use the think tool to reason:
   - Verify dave's dam sector identification makes sense (dam should be near water/lake).
   - Combine dave's sector coordinates with bob's API instructions to build the instruction sequence.
5. Send to headquarters: task "drone", answer: {"instructions": ["instruction1", "instruction2", ...]}

### Phase 3 — Iterate on feedback

6. Read the headquarters response carefully.
7. If there's an error:
   - If the issue is about wrong location/sector → re-spawn dave with feedback, ask for re-analysis
   - If the issue is about wrong API functions/instructions → re-spawn bob with feedback and the error message
   - If the issue is about instruction format or sequence → reason with think tool and adjust yourself
8. Re-send corrected instructions to headquarters.
9. Repeat until you receive a flag ({FLG:...}).

## Rules
- Send answer to headquarters with task "drone" and answer: {"instructions": [...]}
- The drone API docs contain traps — don't try to use every function, only what's needed
- If things get badly stuck, bob should look for a hardReset function in the docs
- Iterate based on headquarters feedback until you receive a flag
- Do NOT guess coordinates — they must come from dave's image analysis

## First step
Think about your approach, then spawn dave and bob in parallel to gather intelligence.
"""


class Mission10(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "drone"

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
