from loguru import logger
import sys
from pathlib import Path

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

USER_MESSAGE = """\
Complete the "domatowo" mission. Find and evacuate a survivor hiding in the ruins of Domatowo.

## Situation

A bombed city. An intercepted radio signal:
> "Przeżyłem. Bomby zniszczyły miasto. Żołnierze tu byli, szukali surowców, zabrali ropę. Teraz jest pusto.
>  Mam broń, jestem ranny. Ukryłem się w jednym z najwyższych bloków. Nie mam jedzenia. Pomocy."

Translation: the survivor is **wounded, armed, hiding in one of the tallest buildings**, with no food.
He is transmitting a **radio signal** — he has equipment capable of broadcasting.

## API

All game actions use `aidevs_headquarters` with `task: "domatowo"` and `answer: {action: "..."}`.

### Known actions (use these exact JSON structures in the `answer` field):

Get full API docs (do this first):
```json
{"action": "help"}
```

Get full 11×11 map:
```json
{"action": "getMap"}
```

Get map filtered to specific symbols only:
```json
{"action": "getMap", "symbols": ["UL"]}
```

Create transporter carrying 2 scouts (costs 5 + 2×5 = 15 pts):
```json
{"action": "create", "type": "transporter", "passengers": 2}
```

Create a solo scout (costs 5 pts):
```json
{"action": "create", "type": "scout"}
```

Inspect current tile (costs 1 pt):
```json
{"action": "inspect"}
```

Get activity log (free):
```json
{"action": "getLogs"}
```

Call rescue helicopter to the tile where survivor was found — DO THIS IMMEDIATELY when found:
```json
{"action": "callHelicopter", "destination": "F6"}
```

**Note:** The move action format is unknown — learn it from `help` before creating any units.

## Resource limits

- **300 action points total** — track remaining after every action
- Max 4 transporters, max 8 scouts
- Costs:
  - Scout creation: 5 pts
  - Transporter creation: 5 pts base + 5 pts per passenger
  - Scout movement: **7 pts per tile** — minimize on-foot movement
  - Transporter movement: **1 pt per tile** — use for bulk transport
  - Inspect current tile: 1 pt
  - Disembark scouts from transporter: 0 pts
- Transporters can only move on street tiles
- Scouts can move on any passable tile

## Strategy

### Phase 1 — Initial plan
1. Use `think` to form initial strategy based on what we know (survivor in tallest building, transporter is cheap, scouts are expensive to walk)
2. Write initial plan to `plan.md`

### Phase 2 — Intel gathering
Step 1 — call `help` first (alone):
- `aidevs_headquarters {action: "help"}` → save full response to `notes/help.md`

Step 2 — reset then get map (sequential: reset must complete before getMap):
- Read `notes/help.md` to find the reset action, then call it to start a fresh game state
- After reset confirms success, call `aidevs_headquarters {action: "getMap"}` → save full response to `notes/map.md`

### Phase 3 — Analysis (sequential: read files first, then think)
Read `notes/help.md` and `notes/map.md` (both in one response).

Then `think` through all of this:
- What does each map symbol mean? The map has markers for buildings of different heights (e.g. 1-floor, 2-floor, 3-floor) and possibly other structure types.
- **Which structures are candidates?** The survivor said "tallest buildings" — but he is also transmitting a radio signal. Think: what type of structure enables radio transmission? Could it be a communications building, radio tower, antenna mast, or other non-residential structure — not just the tallest residential block? Consider ALL structure types on the map, not only standard buildings.
- List every candidate structure coordinate (tall buildings + any structure plausibly linked to radio transmission).
- Where do units spawn? What is the spawn point coordinate?
- Which tiles are streets (transporter-passable)?
- For each candidate tile, what is the nearest street tile?
- What is the shortest transporter path from spawn to cover all candidate clusters?
- Pessimistic budget: if ALL candidates must be inspected, how many points does that cost? Does it fit in 300?
- How many transporters and scouts are optimal? Where are the drop-off points?

Write findings to `notes/analysis.md` (full breakdown with coordinates and point costs).
Update `plan.md` with the concrete execution sequence: unit creation, transporter route, drop-off coordinates, inspection order.

### Phase 4 — Execution loop
Execute the plan step by step:
1. Create units per your analysis
2. Move transporter to first drop-off point (along street route)
3. Disembark scouts
4. Have scouts inspect each tall building tile in the cluster
5. Call `getLogs` to read inspection results
6. Write each API response to `notes/log.md` (append — do not overwrite)
7. Update remaining point budget in `plan.md` after each step

**If any inspection confirms the survivor is found → IMMEDIATELY call `callHelicopter` with that tile coordinate. Do not take any other action first.**

Then move transporter to next cluster and repeat until found.

## Rules

- **Never walk scouts long distances** — if transporter can carry them there, use it (7 pts/tile vs 1 pt/tile)
- **Write to files after every API response** — do not rely on conversation memory alone
- **Track action points** — write remaining budget after every action; abort plan and reassess if budget runs low
- **Inspect only tall buildings** — do not waste points on rubble, streets, or open areas
- **Helicopter call is final** — the moment a survivor is confirmed, `callHelicopter` to that exact coordinate

## First step

Use `think` to form your initial approach, then write it to `plan.md`.
"""


class Mission18(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "domatowo"

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
