import logging
import sys
from pathlib import Path

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

log = logging.getLogger(__name__)

USER_MESSAGE = """\
Complete the "electricity" mission. Solve a 3x3 cable puzzle by rotating tiles to match a target layout.

## Grid addressing

Cells use format AxB (A=row 1-3 top-down, B=column 1-3 left-right):
```
1x1 | 1x2 | 1x3
2x1 | 2x2 | 2x3
3x1 | 3x2 | 3x3
```

## Phase 1: Download both images

1. **Reset and download the CURRENT board** — download_file from:
   ***REMOVED***/data/{{AIDEVS4_HEADQUARTERS_API_KEY}}/electricity.png?reset=1
   Save to notes/electricity_current.png

2. **Download the SOLVED (target) board** — download_file from:
   ***REMOVED***/i/solved_electricity.png
   Save to notes/electricity_target.png

## Phase 2: Analyze both images with vision

3. **Analyze the CURRENT image** using analyze_image with this prompt:
   "This is a 3x3 grid of electrical cable tiles. Each cell has cable lines connecting to some edges. For each cell from 1x1 to 3x3 (row x column, top-to-bottom, left-to-right), list EXACTLY which edges have a cable going to them. Edges are: top, right, bottom, left. Be very precise about where each line leads. Format: 1x1: top, right, bottom"

4. **Analyze the SOLVED image** using analyze_image with the exact same prompt.

5. **Present both analyses to the user** using ask_user. Show the full description of each cell for both CURRENT and SOLVED images and ask the user to confirm before continuing. Wait for confirmation.

## Phase 3: Compare and plan rotations (use think tool)

6. **Use the think tool** to compare both descriptions and calculate rotations:
   - List each cell's edges from CURRENT and SOLVED side by side
   - Calculate how many 90° clockwise rotations each cell needs
   - Rules: one CW rotation shifts edges: top→right, right→bottom, bottom→left, left→top
   - 0 = already matching, 1 = 90° CW, 2 = 180°, 3 = 270° CW (= 90° CCW)
   - Produce a plan: one line per cell that needs rotation, format "AxB: N"

7. **Write the plan** to notes/rotation_plan.txt. Example:
   ```
   1x2: 1
   2x3: 3
   3x1: 2
   ```

## Phase 4: Execute rotations one by one

8. **For each cell in the plan**, send the required number of rotate commands sequentially:
   - Use aidevs_headquarters with task="electricity" and answer={"rotate": "AxB"}
   - One request = one 90° clockwise rotation of that cell
   - If a cell needs 2 rotations, send 2 separate requests for that cell
   - Check EVERY response from headquarters — if any response contains {FLG:...}, the mission is complete

## Phase 5: Get the flag

9. After all planned rotations are sent, headquarters returns either "Done" or a flag {FLG:...}.
   - "Done" means rotations were applied but the puzzle is NOT solved yet — your plan was wrong.
   - {FLG:...} means the puzzle is solved — report the flag and finish.
   - If you get "Done" without a flag, you must reset the board (download with ?reset=1), re-analyze, and try again.

## Important
- There is NO way to see the current state of the board mid-solving. You can only see the INITIAL state (after reset) and the SOLVED target. Your plan must be calculated entirely from comparing those two images.
- Be extremely precise when describing cable positions — the whole solution depends on correct image analysis
- Every aidevs_headquarters response must be checked for a flag
- Do NOT stop until you receive {FLG:...}
"""


class Mission07(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "electricity"

    async def run(self) -> None:
        from src.domain.types import AgentStatus
        from src.entry import init_db, init_logging
        from src.entry.standalone import StandaloneAgent

        init_logging()
        await init_db()

        agent = StandaloneAgent("alice")
        log.info("Starting " + self.get_task_name() + " mission via agent")
        result = await agent.send(USER_MESSAGE)

        while result.status == AgentStatus.WAITING and result.waiting_for:
            for wait in result.waiting_for:
                log.info("Agent asks: %s", result.output)
                answer = input(f"[{wait.tool_name}] Your answer: ")
                result = await agent.deliver(wait.call_id, answer)

        log.info("Agent finished (status=%s):\n%s", result.status, result.output)
