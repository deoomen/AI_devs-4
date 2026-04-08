from loguru import logger
import sys
from pathlib import Path

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

USER_MESSAGE = """\
Complete the "shellaccess" mission. We have access to a remote server with time-archive logs.
Our goal is to find when and where Rafał's body was found, then appear there ONE DAY BEFORE.

## How the server works

Every interaction goes through aidevs_headquarters with:
  task = "shellaccess"
  answer = {"cmd": "<shell command>"}

The server executes the command and returns its stdout. Standard Linux tools are available:
ls, find, cat, grep, head, tail, wc — and also `jq` for JSON files.

**There is no separate final submission step.** When you run an `echo` command that outputs
the correct JSON, the server detects it automatically and returns a flag in the response.
The flag looks like {FLG:...}. Keep sending commands until you see it.

## What to find

Logs are in /data/. Search them for records about finding Rafał (try both "Rafał" and "Rafal").
You need to extract:
- date — the day Rafał was found (YYYY-MM-DD format)
- city — the city where he was found
- longitude — geographic longitude (decimal, e.g. 18.123456)
- latitude — geographic latitude (decimal, e.g. 54.123456)

## Critical date rule

The `date` you submit must be **ONE DAY BEFORE** the date Rafał was found.
Example: if logs say found on 2024-03-15, submit date = "2024-03-14".

## Strategy

### Phase 1 — Explore
1. Start: `ls /data/` to see what files exist
2. If many files: `ls -lh /data/` or `find /data/ -type f | head -30` to understand structure
3. Search: `grep -ri "rafał" /data/` or `grep -ri "rafal" /data/` to locate relevant entries
4. If /data/ contains JSON files: pipe through `jq` (e.g. `cat /data/file.json | jq '.'`)

### Phase 2 — Extract
5. Read the matching file(s) in full or use grep to pull the specific fields
6. Note down: exact date, city, longitude, latitude

### Phase 3 — Compute and submit
7. Subtract 1 day from the found date
8. Run this command (with real values filled in):
   `echo '{"date":"YYYY-MM-DD","city":"city name","longitude":10.000001,"latitude":12.345678}'`
9. The server will validate and return a flag if correct

### Phase 4 — Iterate
10. If the response contains an error or no flag, re-examine the extracted data and retry
11. If date arithmetic is uncertain, reason carefully: subtract exactly 1 calendar day

## Rules
- Always use task="shellaccess" and answer={"cmd": "..."} — never change the task name
- Do NOT submit a structured JSON directly as the answer — always wrap in an echo command
- The flag will arrive in the HTTP response body when the echo outputs correct data
- Save extracted values to notes/ between turns so you don't lose progress

## First step
Think about your approach, then send `ls /data/` to start exploring the server.
"""


class Mission23(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "shellaccess"

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
