from loguru import logger
import sys
from pathlib import Path

from missions.base_mission import BaseMission

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

USER_MESSAGE = """\
Complete the "foodwarehouse" mission. The city needs file is already saved at \
`shared/mission20/food4cities.json`.

All warehouse API calls go through `aidevs_headquarters` with `task: "foodwarehouse"` \
and `answer` set to the warehouse tool object, for example:
```json
{ "tool": "help" }
{ "tool": "database", "query": "show tables" }
{ "tool": "orders", "action": "create", ... }
```

---

## Phase 0 — Reset

Before anything else, send a reset to start from a clean state:
```json
{ "tool": "reset" }
```

---

## Phase 1 — Gather information (parallel)

Fire all three in a single response:
1. `read_file shared/mission20/food4cities.json` — city names + exact goods and quantities needed
2. `aidevs_headquarters` with `{ "tool": "help" }` — learn the full API: what parameters \
signatureGenerator requires, what fields orders.create expects, etc.
3. `aidevs_headquarters` with `{ "tool": "database", "query": "show tables" }` — get table names

Save the help response and table list to `notes/`.

---

## Phase 2 — Plan

Use `think` to build a complete execution plan:
- How many cities, what goods and quantities each needs
- Which DB tables are likely to contain destination codes and user data
- What the signatureGenerator requires (from the help response)
- What `creatorID` and `signature` are needed per order

Write the plan to `/plan.md`.

---

## Phase 3 — Prepare SQL queries (delegate to Heidi)

Delegate to the `heidi` agent. Give her:
- The full list of table names from Phase 1
- What data you need: destination codes mapped to city names, and user row(s) \
needed to generate the signature (login, password, or whatever fields help specifies)

Heidi will write `SELECT *` queries to her `outbox/queries.md`. Read that file after she finishes.

---

## Phase 4 — Execute DB queries (parallel)

Fire all of Heidi's queries simultaneously — one `aidevs_headquarters` call per query, all in one response:
```json
{ "tool": "database", "query": "SELECT * FROM table1;" }
{ "tool": "database", "query": "SELECT * FROM table2;" }
```

Save raw results to `notes/db_results.md`.

Use `think` to extract:
- city name → destination code mapping
- user row: creatorID, and the fields needed for the signature

Save the extracted data to `notes/data.md`.

---

## Phase 5 — Generate signatures (parallel)

Using the user data from Phase 4 and the signatureGenerator parameters from help, \
generate one signature per city. Fire all calls in a single response:
```json
{ "tool": "signatureGenerator", ... }  ← one per city
```

Save city → signature mapping to `notes/signatures.md`.

---

## Phase 6 — Create orders (parallel)

Fire one `orders.create` per city, all in a single response:
```json
{
  "tool": "orders",
  "action": "create",
  "title": "Dostawa dla <city>",
  "creatorID": <id>,
  "destination": "<code>",
  "signature": "<sha1>"
}
```

Save the returned order ID for each city to `notes/order_ids.md`.

---

## Phase 7 — Append items (parallel)

Fire one `orders.append` per city using batch mode, all in a single response:
```json
{
  "tool": "orders",
  "action": "append",
  "id": "<order_id>",
  "items": { "chleb": 45, "woda": 120, ... }
}
```

Use exact quantities from `food4cities.json` — no rounding, no extras.

---

## Phase 8 — Finalize

Send:
```json
{ "tool": "done" }
```

HQ will validate all orders. If the response contains a flag — you are done, report it.

---

## Error recovery

If `done` returns errors:
- Use `think` to analyse: which city is wrong? wrong quantity? wrong destination? \
wrong signature? wrong creatorID?
- Fix only the affected order(s): delete and recreate, or append the missing delta
- Retry `done`
- If the state is badly broken, call `reset` and restart from Phase 3 \
(data is already in `notes/`, skip the DB queries)

Do not give up after a single failure — iterate until the flag is received.

Task name for all API calls: **foodwarehouse**
"""


class Mission20(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "foodwarehouse"

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
