import csv
import logging
from missions.base_mission import BaseMission
from pathlib import Path
from pydantic import BaseModel
from services.OpenRouter import OpenRouterClient

log = logging.getLogger(__name__)

MISSION_DIR = Path(__file__).parent
AVAILABLE_TAGS = """
- IT: praca związana z technologią, programowaniem, systemami informatycznymi, infrastrukturą techniczną
- transport: praca związana z przewozem towarów lub osób, logistyką, spedycją
- edukacja: praca związana z nauczaniem, szkoleniem, przekazywaniem wiedzy, wychowaniem
- medycyna: praca związana z ochroną zdrowia, leczeniem, diagnozowaniem, opieką medyczną
- praca z ludźmi: praca wymagająca bezpośredniego kontaktu i współpracy z innymi ludźmi
- praca z pojazdami: praca przy obsłudze, naprawie lub prowadzeniu pojazdów mechanicznych
- praca fizyczna: praca wymagająca wysiłku fizycznego, pracy rąk, obsługi maszyn lub narzędzi
"""


class PersonTags(BaseModel):
    person_id: int
    tags: list[str]


class TaggingResponse(BaseModel):
    results: list[PersonTags]


class Mission01(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._openrouter = OpenRouterClient(api_key=self.config.openrouter_api_key)

    def get_task_name(self) -> str:
        return "people"

    def filter_csv(self, path: Path) -> list[dict]:
        results = []
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["gender"] != "M":
                    continue

                birth_year = int(row["birthDate"].split("-")[0])
                age_in_2026 = 2026 - birth_year
                if not (20 <= age_in_2026 <= 40):
                    continue

                if row["birthPlace"] != "Grudziądz":
                    continue

                results.append(row)
        log.info("Filtered %d records", len(results))
        return results

    async def tag_people(self, people: list[dict]) -> list[dict]:
        client = self._openrouter

        indexed = list(enumerate(people))

        people_list = "\n".join(
            f"person_id={i}, job description: {row['job']}"
            for i, row in indexed
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "Jesteś ekspertem od klasyfikacji zawodów. "
                    "Przypisz tagi do każdej osoby na podstawie opisu jej pracy.\n\n"
                    "Dostępne tagi (możesz przypisać więcej niż jeden):\n"
                    f"{AVAILABLE_TAGS}\n"
                    "Używaj wyłącznie tagów z powyższej listy."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Przypisz tagi do poniższych osób na podstawie opisu ich pracy:\n\n"
                    f"{people_list}"
                ),
            },
        ]

        log.info("Sending %d people to OpenRouter for tagging", len(people))
        result = await client.chat_structured(messages=messages, response_model=TaggingResponse)
        log.info("Tagging complete")
        tags_by_id = {entry.person_id: entry.tags for entry in result.results}
        for i, row in indexed:
            row["tags"] = ",".join(tags_by_id.get(i, []))
        return people

    async def run(self) -> None:
        url = "***REMOVED***/data/{}/people.csv".format(self.config.aidevs4_headquarters_api_key)
        csv_path = await self.download_file(url, MISSION_DIR / "people.csv")
        filtered_path = MISSION_DIR / "people_filtered.csv"

        if filtered_path.exists():
            log.info("Filtered CSV already exists at %s, loading", filtered_path)
            with filtered_path.open(newline="", encoding="utf-8") as f:
                people = list(csv.DictReader(f))
        else:
            log.info("Filtered CSV does not exist, filtering and tagging")
            people = self.filter_csv(csv_path)
            self.save_csv(filtered_path, people)

            people = await self.tag_people(people)
            self.save_csv(filtered_path, people)

        transport = [p for p in people if "transport" in p.get("tags", "").split(",")]
        log.info("Transport workers (%d): %s", len(transport), transport)
        suspects_path = MISSION_DIR / "suspects_people.csv"
        self.save_csv(suspects_path, transport)
        log.info("Saved %d transport suspects to %s", len(transport), suspects_path)

        report = [
            {
                "name": p["name"],
                "surname": p["surname"],
                "gender": p["gender"],
                "born": int(p["birthDate"].split("-")[0]),
                "city": p["birthPlace"],
                "tags": p.get("tags", "").split(","),
            }
            for p in transport
        ]
        result = await self.report_to_headquarter(report)
        log.info("Headquarter response: %s", result)
