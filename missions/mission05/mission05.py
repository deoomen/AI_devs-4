import logging
import sys
from pathlib import Path

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

log = logging.getLogger(__name__)

USER_MESSAGE = """\
Complete the "railway" mission at AIDevs headquarters. You need to activate railway route with code "X-01".

1. Start by sending action "help" to the railway task and carefully read the response
2. The API is self-documenting — the response describes all available actions, parameters, and the required call sequence
3. Follow the documented sequence exactly — use only action names and parameter names from the response, do not guess
4. If you get HTTP 503, wait and retry the same request
5. Respect rate limits — check response headers, wait for reset before next call
6. When a response contains a flag in format {{FLG:...}}, the mission is complete — report it back
"""


class Mission05(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "railway"

    async def run(self) -> None:
        from src.domain.types import AgentStatus
        from src.runtime.standalone import StandaloneAgent

        agent = StandaloneAgent("alice")
        log.info("Starting railway mission via agent")
        result = await agent.send(USER_MESSAGE)

        while result.status == AgentStatus.WAITING and result.waiting_for:
            for wait in result.waiting_for:
                log.info("Agent asks: %s", result.output)
                answer = input(f"[{wait.tool_name}] Your answer: ")
                result = await agent.deliver(wait.call_id, answer)

        log.info("Agent finished (status=%s):\n%s", result.status, result.output)
