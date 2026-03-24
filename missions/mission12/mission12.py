from loguru import logger
import sys
from pathlib import Path

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

USER_MESSAGE = """\
Complete the "firmware" mission. Fix and run the ECCS firmware on a remote virtual machine to obtain a confirmation code.

## Context
The ECCS (Emergency Core Cooling System) firmware has been loaded into a virtual machine. The firmware binary exists but won't run correctly — you need to find a password, reconfigure it, and start it. When it runs successfully, it outputs a confirmation code in format `ECCS-xxxx...` that you must send to headquarters.

## How to interact with the VM
You have access to a remote Linux shell via HTTP API. Send commands using http_request:
- **Method**: POST
- **URL**: {{AIDEVS4_HEADQUARTERS_SYSTEM_URL}}/api/shell
- **Body**: {"apikey": "{{AIDEVS4_HEADQUARTERS_API_KEY}}", "cmd": "<your command>"}

All `{{...}}` placeholders are resolved automatically at execution time in ALL tool arguments (both URL and body). Use them literally — do NOT try to guess or replace them yourself.

**CRITICAL**: This is a non-standard, restricted Linux. Do NOT assume standard commands work. Your very first command MUST be `help` to learn what commands are available. Pay close attention to file editing — it works differently than in standard Linux.

## Security rules — VIOLATION = BAN + VM RESET
- You are a regular user (no root)
- **FORBIDDEN directories** — NEVER read, list, or access: `/etc`, `/root`, `/proc/`
- If you find a `.gitignore` file in any directory, you MUST respect it — do NOT touch, read, list, or access any files or directories listed in it
- Violating these rules instantly bans you (access blocked for N seconds) and resets the VM to initial state, losing all your progress
- When in doubt, DON'T access it

## Step-by-step strategy

### Phase 1 — Reconnaissance
1. Run `help` to learn available commands
2. Explore the filesystem carefully (avoid forbidden dirs!). Start with `/opt/firmware/cooler/`
3. Try running `/opt/firmware/cooler/cooler.bin` — observe what happens (it will likely fail or ask for something)
4. Check for `.gitignore` files in directories you explore — read them and respect their contents

### Phase 2 — Find the password
5. The binary needs a password to run. The password is stored in several places in the system.
6. Search the filesystem for clues — look in home directories, readable system locations, documentation files, notes, etc.
7. Remember: stay away from `/etc`, `/root`, `/proc/`

### Phase 3 — Configure and run
8. Read `settings.ini` (likely near the binary in `/opt/firmware/cooler/`)
9. Reconfigure `settings.ini` as needed to make the firmware work correctly (use whatever file editing command the `help` output described)
10. Run the binary again with the correct password/configuration
11. Extract the `ECCS-...` confirmation code from the output

### Phase 4 — Report
12. Send the code to headquarters: task "firmware", answer: {"confirmation": "ECCS-the-code-you-got"}

## Rules
- Send answer to headquarters with task "firmware" and answer: {"confirmation": "<ECCS code>"}
- The expected code format is: `ECCS-` followed by a long hex/alphanumeric string
- Use `reboot` command if you mess up the VM state and need to start fresh
- Work sequentially — each shell command depends on the previous output
- Save important findings to notes/ files as you go, so you don't lose track
- If you get banned (API returns an error about ban), wait the specified duration and retry
- Do NOT guess or fabricate the ECCS code — it must come from actually running the binary

## First step
Use the think tool to acknowledge the plan, then send the `help` command to the VM to learn what's available.
"""


class Mission12(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "firmware"

    async def run(self) -> None:
        from src.domain.types import AgentStatus
        from src.entry import init_db, init_logging
        from src.entry.standalone import StandaloneAgent

        init_logging()
        await init_db()

        agent = StandaloneAgent("alice")
        logger.info("Starting \"{}\" mission via agent (session={})", self.get_task_name(), agent.session_id)
        result = await agent.send(USER_MESSAGE)

        while result.status == AgentStatus.WAITING and result.waiting_for:
            for wait in result.waiting_for:
                logger.info("Agent asks: {}", result.output)
                answer = input(f"[{wait.tool_name}] Your answer: ")
                result = await agent.deliver(wait.call_id, answer)

        logger.info("Agent finished (status={}):\n{}", result.status, result.output)
