from abc import ABC, abstractmethod

from config import Config, load_config


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
