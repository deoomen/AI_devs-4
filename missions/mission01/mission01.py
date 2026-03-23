from loguru import logger
import sys
from pathlib import Path

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

USER_MESSAGE = """\
Complete the "people" mission at AIDevs headquarters.

## Goal
Find people involved in organizing transports between power plants.

## Data source
CSV file: exactly {{AIDEVS4_HEADQUARTERS_SYSTEM_URL}}/data/{{AIDEVS4_HEADQUARTERS_API_KEY}}/people.csv download it and save.
Skip placeholder as this is a system feature and will be handle when run.

## Criteria
We must filter csv file for people who match ALL of these conditions:
- Male (gender = "M")
- Born in Grudziądz
- Aged 20-40 in 2026 (birth year between 1986 and 2006)
- Working in transport

For filtering use yout tools, do not send whole people.csv to LLM.

## Tagging
Each person's job description must be tagged. A person can have multiple tags. \
Available tags with descriptions:
- IT: praca związana z technologią, programowaniem, systemami informatycznymi
- transport: praca związana z przewozem towarów lub osób, logistyką, spedycją
- edukacja: praca związana z nauczaniem, szkoleniem, przekazywaniem wiedzy
- medycyna: praca związana z ochroną zdrowia, leczeniem, diagnozowaniem
- praca z ludźmi: praca wymagająca bezpośredniego kontaktu i współpracy z innymi ludźmi
- praca z pojazdami: praca przy obsłudze, naprawie lub prowadzeniu pojazdów mechanicznych
- praca fizyczna: praca wymagająca wysiłku fizycznego, pracy rąk, obsługi maszyn lub narzędzi

Only people tagged with "transport" (who also match all other criteria) should be reported.

## Report format
Send to headquarters with task name "people". The answer is an array of objects:
{"name": "Jan", "surname": "Kowalski", "gender": "M", "born": 1987, "city": "Grudziądz", "tags": ["transport", "praca z pojazdami"]}

Field "born" is an integer (year only). Field "tags" is an array of strings.
"""


class Mission01(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "people"

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
