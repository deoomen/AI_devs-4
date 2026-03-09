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
        log.info("Downloading CSV from %s -> %s", url, dest)

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            dest.write_bytes(response.content)

        log.info("CSV saved (%d bytes)", dest.stat().st_size)
        return dest

    async def run(self) -> None:
        await self.download_csv()
