import logging
from missions.base_mission import BaseMission

log = logging.getLogger(__name__)


class Mission05(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "railway"

    async def run(self) -> None:
        pass
