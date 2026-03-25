from loguru import logger
import sys
from pathlib import Path

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

USER_MESSAGE = """\
Complete the "reactor" mission. Guide a transport robot carrying a cooling device through a reactor zone to a target slot.

## Map mechanics
- Grid: 7 columns x 5 rows.
- Robot moves ONLY along the bottom row (row 5).
- Start position: column 1, row 5 (marked P).
- Goal: column 7, row 5 (marked G).
- Reactor blocks (B): each occupies exactly 2 cells, moves cyclically up/down.
  - When a block reaches the top, it reverses down. When it reaches the bottom, it reverses up.
  - Blocks move ONE step each time you send ANY command (including "wait").
- Map symbols: P=robot, G=goal, B=block, .=empty

## Commands (send one at a time)
- "start" — initialize the game (MUST be sent first)
- "right" — move robot one column to the right (toward goal)
- "left" — move robot one column to the left (retreat)
- "wait" — robot stays, but blocks still move
- "reset" — reset the game entirely

## How to interact with the API
Use the aidevs_headquarters tool for EVERY command:
- task: "reactor"
- answer: {"command": "start"} (or "right", "left", "wait", "reset")

The API response contains the current map state showing block positions and their movement directions. Read it carefully after EVERY command.

## Navigation algorithm
1. Send "start" and read the returned map.
2. For each step, analyze the map and decide:
   a) Look at your CURRENT column and the NEXT column (to the right).
   b) Check if any block occupies or WILL occupy row 5 in the next column after the next move.
   c) Also check if any block will reach row 5 in your CURRENT column after the next move.
   d) **If the next column's row 5 will be clear** → send "right"
   e) **If the next column is dangerous but current position is safe** → send "wait" (blocks move, situation may improve)
   f) **If BOTH current and next column are dangerous** → send "left" (retreat)
3. Repeat until you reach column 7 (goal).

## Critical safety rules
- A block at row 4 moving DOWN will be at row 5 next step — DANGER.
- A block at row 5 — already dangerous, do NOT move into that column.
- A block at row 3 moving DOWN will be at row 4 next step — safe for now but watch it.
- Each block is 2 cells tall. If a block's top is at row 4, its bottom is at row 5 — DANGER.
- When in doubt, "wait" is safer than "right". Be patient.
- If you get crushed, send "reset" and then "start" to try again.

## Thinking approach
Before each command, use the think tool to:
1. Parse the current map — identify where blocks are and which direction they're moving.
2. Determine robot's current column.
3. Check safety of current position AND next column for the next step.
4. Choose the safest action.

## Success
Keep going until the API response indicates you've reached the goal and returns a flag ({FLG:...}).
Report the flag when done.

## First step
Send "start" to initialize the game, then begin navigating.
"""


class Mission13(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "reactor"

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
