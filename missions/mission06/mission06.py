from loguru import logger
import sys
from pathlib import Path

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

USER_MESSAGE = """\
Complete the "categorize" mission. You must classify 10 items as dangerous (DNG) or neutral (NEU).

## Steps

1. **Reset** — send to aidevs_headquarters: task="categorize", answer={"prompt": "reset"}
2. **Download CSV** — download from: {{AIDEVS4_HEADQUARTERS_SYSTEM_URL}}/data/{{AIDEVS4_HEADQUARTERS_API_KEY}}/categorize.csv
3. **Read the CSV** — each row has an id and a description
4. **For EACH row**, build a concrete prompt with that row's id and description baked in, then send it:
   - aidevs_headquarters: task="categorize", answer={"prompt": "your prompt with actual id and description for this row"}
   - The hub passes your prompt to a tiny model (100 token context). The model must output exactly DNG or NEU.
   - Read the response — if it says wrong classification, you'll need to reset and start over with an improved prompt.
5. After all 10 items are classified correctly, the hub returns a flag {FLG:...}.
6. **If any item fails** — reset (step 1), download fresh CSV (contents change!), adjust your prompt template, and retry all 10.

## Classification rules
- Dangerous items (weapons, explosives, toxic chemicals, etc.) → DNG
- Neutral items (food, clothing, tools, etc.) → NEU
- **EXCEPTION: anything related to reactor cassettes/parts → always NEU** (we're smuggling these)

## Prompt tips
- The prompt + id + description must fit in ~100 tokens total — be very concise
- Use English — more token-efficient
- Structure: short instruction, then the item data, then "Answer:"
- The reactor exception must be explicit in the prompt
- Token budget is tight (1.5 PP for all 10 calls) — keep prompts short
"""


class Mission06(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "categorize"

    async def run(self) -> None:
        from src.domain.types import AgentStatus
        from src.entry import init_db, init_logging
        from src.entry.standalone import StandaloneAgent

        init_logging()
        await init_db()

        agent = StandaloneAgent("alice")
        logger.info("Starting \"{}\" mission via agent", self.get_task_name())
        result = await agent.send(USER_MESSAGE)

        while result.status == AgentStatus.WAITING and result.waiting_for:
            for wait in result.waiting_for:
                logger.info("Agent asks: {}", result.output)
                answer = input(f"[{wait.tool_name}] Your answer: ")
                result = await agent.deliver(wait.call_id, answer)

        logger.info("Agent finished (status={}):\n{}", result.status, result.output)
