from loguru import logger
import sys
from pathlib import Path

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

USER_MESSAGE = """\
Complete the "savethem" mission. Plan an optimal route for a messenger to reach the city of Skolwin.

## Context
We need to send a human messenger to negotiate with the city of Skolwin. You must plan the route: \
choose a vehicle, navigate a 10x10 terrain grid, and balance fuel vs food consumption to arrive safely.

## Resources & Vehicle Rules
- **10 food portions** and **10 fuel units** available
- Each move costs food (always) and fuel (unless walking on foot)
- Faster vehicles burn more fuel per move but save food (shorter trip)
- Walking burns zero fuel but costs more food (slower = longer trip)
- You choose **exactly one vehicle** at the start (first element of the answer array)
- You can **exit the vehicle at any point** and continue on foot
- Once you exit, you **cannot get back in** — the switch is permanent
- This means you might drive part of the route, then walk the rest

## Tool Discovery
You do NOT have direct access to mission tools. Instead, use **toolsearch** to discover them.

Call toolsearch via http_request:
- Method: POST
- URL: {{AIDEVS4_HEADQUARTERS_SYSTEM_URL}}/api/toolsearch
- Body: {"apikey": "{{AIDEVS4_HEADQUARTERS_API_KEY}}", "query": "your search query here"}

All discovered tools use the **same interface**: POST to their URL with {"apikey": "{{AIDEVS4_HEADQUARTERS_API_KEY}}", "query": "your question"}.

Important: each tool returns only the **3 best matching results**, not everything. You may need to query \
the same tool multiple times with different queries to get all the information you need.

All tools communicate in **English only**.

## Shared cache (persistent across runs)
The `shared/` directory persists between agent runs. Before making any API calls:
1. Check `shared/` with list_files — if any files already exist, **read them and skip re-fetching that data**.
2. Only call toolsearch/tools for information you don't already have cached.
3. When you gather new data, always save it to `shared/` (not just `notes/`) so future runs can reuse it.

## Strategy

### Phase 0 — Check cache
1. List files in `shared/` to see what data is already available from previous runs.
2. Read any cached files. If map, vehicles, and rules are all cached, skip directly to Phase 3.

### Phase 1 — Discover tools (skip if shared/tools.md exists)
3. Use think tool to plan what information you need: map data, vehicle specs, terrain rules, movement costs.
4. Search toolsearch with varied queries to discover all relevant tool endpoints:
   - "map terrain grid" — to find a map/terrain tool
   - "vehicles transport fuel" — to find vehicle specifications
   - "movement rules costs" — to find movement/game rules
   Try different keyword combinations if initial searches don't cover everything.
5. Save discovered tool endpoints and descriptions to **shared/tools.md**.

### Phase 2 — Gather intelligence (skip items already cached in shared/)
6. Query discovered tools to collect ALL needed information:
   - **Map**: Get the full 10x10 grid. Identify start position and Skolwin location. Note terrain types (rivers, trees, rocks = impassable?).
   - **Vehicles**: Get ALL vehicle options with their fuel consumption per move. Query multiple times with different terms if needed.
   - **Movement rules**: How does walking work? What costs food/fuel per step? Which terrain types block movement?
7. Save all gathered data to **shared/** files (shared/map.md, shared/vehicles.md, shared/rules.md).

### Phase 3 — Plan the route (shortest path problem)
This is a **shortest path / BFS problem** on a 10x10 grid with obstacles. Approach it methodically:

8. Use think tool extensively to reason about the optimal path:
   - Draw the full 10x10 grid with terrain markers (use a text grid, label rows 0-9 and cols 0-9).
   - Mark start (S) and destination Skolwin (D) clearly.
   - Mark impassable cells (rivers, rocks, trees, etc.) as blocked.
   - **Find the shortest passable path** (fewest moves) from S to D using BFS-like reasoning — explore neighbors level by level, avoid obstacles.
   - Count the total number of moves for the shortest path.
   - For each vehicle, calculate resource costs for the FULL route driven: total_fuel = moves × fuel_per_move, total_food = moves × food_per_move.
   - For walking the FULL route: total_fuel = 0, total_food = moves × walk_food_rate.
   - For **hybrid** (drive N steps, walk the rest): fuel = N × vehicle_fuel_rate, food = N × vehicle_food_rate + (total_moves - N) × walk_food_rate. Find the split point N where both fuel ≤ 10 and food ≤ 10.
   - Pick the vehicle + strategy that completes the route within budget.
   - Convert the path into direction steps: up/down/left/right.
9. Write planned route to notes/route.md.

### Phase 4 — Submit answer
8. Send to headquarters: task "savethem", answer as JSON array: ["vehicle_name", "direction", "direction", ...]
   - Directions are: "up", "down", "left", "right"
   - First element MUST be the vehicle name
9. Check the response carefully.

### Phase 5 — Iterate on feedback
10. If the answer is wrong:
    - Re-examine the map, terrain rules, or vehicle data — you may be missing info.
    - Query tools again with different queries to find missed details.
    - Recalculate the route.
    - Resubmit.
11. Repeat until you receive a flag ({FLG:...}).

## Rules
- Use {{AIDEVS4_HEADQUARTERS_API_KEY}} as the apikey in ALL tool/toolsearch requests (it will be resolved automatically)
- Answer format: ["vehicle_name", "right", "up", "left", ...] — vehicle name first, then directions
- Task name for headquarters: "savethem"
- Do NOT guess — base everything on data from the discovered tools
- Query tools multiple times with different queries to ensure you have complete information
- Think carefully about resource optimization before submitting

## First step
Use the think tool to plan your approach, then start discovering tools via toolsearch.
"""


class Mission15(BaseMission):
    def get_task_name(self) -> str:
        return "savethem"

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
