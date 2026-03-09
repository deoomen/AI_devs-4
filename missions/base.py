import csv
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

    @abstractmethod
    def get_task_name(self) -> str:
        """Get the name of the task."""
        raise NotImplementedError

    @abstractmethod
    async def run(self) -> None:
        """Execute the mission."""
        raise NotImplementedError

    def save_csv(self, path: Path, data: list[dict]) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        log.info("CSV saved to %s (%d rows)", path, len(data))

    def report_to_headquarter(self, report: dict | list[dict]) -> str:
        log.info("Reporting to headquarter")
        headquarter = AIdevs4()

        return headquarter.verify(
            self.get_task_name(),
            report,
        )
