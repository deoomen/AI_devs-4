from loguru import logger
import sys
from pathlib import Path

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

USER_MESSAGE = """\
Complete the "okoeditor" mission. You must make three specific data changes inside the OKO surveillance system \
using its API — but first you need to explore the web panel to understand the data structure and collect the IDs you'll need.
All data like urls provieded in format like placeholders like {{XXX}} will be evaluated by the agent at runtime.

## Context

The OKO system is a surveillance control center that monitors unusual incidents across the country.
We have obtained login credentials to its web panel. The panel is READ-ONLY — you must not modify anything through it \
(operators would detect it immediately). All changes must go through the Centrala API (/verify).

## Phase 1 — Understand the API

Call the Centrala API with `action: "help"` to learn all available operations and their parameters.
Save the full help output to notes/api_help.md.

## Phase 2 — Explore the web panel

Log in to the OKO web panel at {{OKO_PANEL_URL}} using credentials:
- username: {{OKO_PANEL_USERNAME}}
- password: {{OKO_PANEL_PASSWORD}}
- access key (if required): {{AIDEVS4_HEADQUARTERS_API_KEY}}

Explore all available pages (reports, tasks, incidents, dashboard — follow all navigation links).
For each page extract and record: IDs/UUIDs, city names, classifications, statuses, descriptions.
We are specifically interested in anything related to cities **Skolwin** and **Komarowo**.
Save all findings (IDs, UUIDs, current values, source URLs) to notes/panel_findings.md.

## Phase 3 — Plan changes

Use the think tool to map the panel findings to the three required changes:
1. Which report ID corresponds to Skolwin — and what is the correct "animals" classification value from the API help?
2. Which task ID corresponds to Skolwin — and what parameters mark it as done?
3. What parameters are needed to create a new incident for Komarowo?

## Phase 4 — Execute three changes

Make all three modifications via the Centrala API (task: "okoeditor"):

1. **Change the Skolwin report classification** — from "seen vehicles and people" to animals.
2. **Mark the Skolwin task as done** — set its status to completed and update its content to mention that animals \
(e.g. beavers) were seen there.
3. **Add a new incident for Komarowo** — report detected human movement in the vicinity of Komarowo \
(this is to redirect operator attention to an uninhabited area and away from Skolwin).

After each change, check the API response for confirmation or errors. If something fails, re-read the api_help.md \
and adjust parameters.

## Phase 5 — Finalize

Once all three changes are confirmed, call the API with `action: "done"`. \
Read the response for a flag or further instructions. Iterate if needed.

## Rules
- Task name for all Centrala API calls: "okoeditor"
- All answer payloads wrap an action object: {"action": "...", ...}
- Web panel is READ-ONLY — only explore and extract data, never submit forms that modify data (operators would detect it and ban us)
- If the API returns an error, diagnose it from the error message before retrying
- Save important intermediate state (API help, frank's findings) to notes/ so you don't lose progress
"""


class Mission16(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "okoeditor"

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
