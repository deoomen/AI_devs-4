from missions.base_mission import BaseMission

class Mission03(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "proxy"

    async def run(self) -> None:
        await self.headquarter.verify(
            self.get_task_name(),
            {
                "url": self.config.proxy_agent_url + "/proxy-agent",
                "sessionID": "S01E03",
            }
        )
