import csv
import logging
from pathlib import Path

import httpx

from missions.base import BaseMission

log = logging.getLogger(__name__)

MISSION_DIR = Path(__file__).parent


class Mission01(BaseMission):
    def get_task_name(self) -> str:
        return "people"

    async def download_csv(self) -> Path:
        url = "***REMOVED***/data/{}/people.csv".format(self.config.headquarters_api_key)

        dest = MISSION_DIR / "people.csv"
        if dest.exists():
            log.info("CSV already exists at %s, skipping download", dest)
            return dest

        log.info("Downloading CSV from %s -> %s", url, dest)

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            dest.write_bytes(response.content)

        log.info("CSV saved (%d bytes)", dest.stat().st_size)
        return dest

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

    async def run(self) -> None:
        csv_path = await self.download_csv()
        self.filter_csv(csv_path)
