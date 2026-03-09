from abc import ABC, abstractmethod


class BaseMission(ABC):
    """Base contract for all mission implementations."""

    @abstractmethod
    def get_task_name(self) -> str:
        """Get the name of the task."""
        raise NotImplementedError

    @abstractmethod
    async def run(self) -> None:
        """Execute the mission."""
        raise NotImplementedError
