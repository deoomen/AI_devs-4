"""Mission 14 — negotiations

Registers tool endpoints with headquarters, then polls for the flag.
The actual tool server runs separately via: uvicorn missions.mission14.tool_server:app --port 3001
"""

import asyncio

from loguru import logger

from missions.base_mission import BaseMission

TOOL_DESCRIPTION = (
    "Search for cities that sell a specific item. "
    "Send the item name or description in the 'params' field (natural language). "
    "Returns a comma-separated list of city names that offer this item."
)


class Mission14(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.ngrok_url: str = ""

    def get_task_name(self) -> str:
        return "negotiations"

    async def _register_tools(self) -> str:
        """Register our tool endpoint with headquarters."""
        tool_url = f"{self.ngrok_url}/api/search"
        logger.info("Registering tool: {}", tool_url)

        answer = {
            "tools": [
                {
                    "URL": tool_url,
                    "description": TOOL_DESCRIPTION,
                },
            ]
        }
        return await self.report_to_headquarter(answer)

    async def _check_result(self) -> str:
        """Poll headquarters for the async result."""
        return await self.report_to_headquarter({"action": "check"})

    async def run(self) -> None:
        # 1. Discover ngrok public URL
        self.ngrok_url = self.config.proxy_agent_url

        # 2. Register tools with headquarters
        logger.info("Registering tools...")
        reg_result = await self._register_tools()
        logger.info("Registration result: {}", reg_result)

        # 3. Wait for the external agent to use our tools
        logger.info("Waiting 60s for the external agent to finish...")
        await asyncio.sleep(60)

        # 4. Check result
        logger.info("Checking result...")
        result = await self._check_result()
        logger.info("Result: {}", result)
