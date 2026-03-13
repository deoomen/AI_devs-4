import csv
import httpx
import logging
from abc import ABC, abstractmethod
from config import Config, load_config
from pathlib import Path
from services.AIdevs4 import AIdevs4

log = logging.getLogger(__name__)


class BaseMission(ABC):
    """Base contract for all mission implementations."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or load_config()
        self.headquarter = AIdevs4(config=self.config)

    @abstractmethod
    def get_task_name(self) -> str:
        """Get the name of the task."""
        raise NotImplementedError

    @abstractmethod
    async def run(self) -> None:
        """Execute the mission."""
        raise NotImplementedError

    async def download_file(self, url: str, dest: Path) -> Path:
        if dest.exists():
            log.info("File already exists at %s, skipping download", dest)
            return dest

        log.info("Downloading file -> %s", dest)

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            dest.write_bytes(response.content)

        log.info("File saved (%d bytes)", dest.stat().st_size)
        return dest

    def save_csv(self, path: Path, data: list[dict]) -> None:
        if not data:
            log.warning("save_csv called with empty data, skipping %s", path)
            return
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        log.info("CSV saved to %s (%d rows)", path, len(data))

    async def report_to_headquarter(self, report: dict | list[dict]) -> str:
        log.info("Reporting to headquarter")

        return await self.headquarter.verify(
            self.get_task_name(),
            report,
        )
