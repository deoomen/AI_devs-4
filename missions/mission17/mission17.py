import asyncio
import json
import sys
from pathlib import Path

import httpx
from loguru import logger

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

# ── Agent phase prompt ────────────────────────────────────────────────────────
# The agent only collects and analyzes data. It does NOT open the service window.
# The time-critical submission (start → unlock codes → config) is handled below in Python.

AGENT_PROMPT = """\
Your job is to collect and analyze data for the **windpower** mission, then write \
the computed turbine schedule to a file. You will NOT open the service window or \
submit any config — that will be handled separately.

## Step 1 — Learn the API
Call action "help" to get the full API documentation. Save the complete response \
to notes/help.json.

## Step 2 — Trigger report generation (in parallel)
Using the action names from the help docs, trigger ALL available report-generation \
endpoints in a single response (parallel calls). Each will return a queue ID or \
confirmation. Note what reports are available and how to fetch them.

## Step 3 — Fetch reports (in parallel)
Fetch all generated reports in a single response. Each report can only be fetched once. \
Save each report to notes/ (e.g. notes/weather.json, notes/turbine.json, notes/power.json).

## Step 4 — Analyze
Use the think tool to reason through the data:
- Identify every time window where wind speed is dangerously high — these need \
  protective mode (high pitchAngle, turbineMode "idle").
- The turbine resets ~1 hour after each major storm, so you may need multiple \
  protective entries per storm period.
- Find the **first** time window where conditions allow generating the required \
  power output — this needs production mode with optimal pitchAngle.
- Hours always use 00 minutes and 00 seconds.
- For each entry, record the **exact wind speed in m/s** from the weather forecast \
  at that specific hour — you will need it.

## Step 5 — Write schedule to outbox
Write your computed schedule to **outbox/windpower_schedule.json** in this exact format \
(windMs is the wind speed from the forecast at that hour, required for code generation):
```json
{
  "entries": [
    {
      "datetime": "2026-03-24 18:00:00",
      "startDate": "2026-03-24",
      "startHour": "18:00:00",
      "pitchAngle": 90,
      "turbineMode": "idle",
      "windMs": 18.5
    },
    {
      "datetime": "2026-03-24 20:00:00",
      "startDate": "2026-03-24",
      "startHour": "20:00:00",
      "pitchAngle": 0,
      "turbineMode": "production",
      "windMs": 8.2
    }
  ]
}
```

Then finish. Do not call "start", do not call "config", do not call "done". \
Just write the file and stop.
"""


# ── Python submission phase ───────────────────────────────────────────────────

async def _hq(client: httpx.AsyncClient, url: str, api_key: str, answer: dict) -> dict:
    payload = {"apikey": api_key, "task": "windpower", "answer": answer}
    resp = await client.post(url, json=payload)
    data = resp.json()
    logger.info("windpower API → {}", data)
    return data


async def _submit_schedule(schedule_path: Path, verify_url: str, api_key: str) -> None:
    raw = json.loads(schedule_path.read_text())
    entries: list[dict] = raw["entries"]
    logger.info("Loaded {} schedule entries", len(entries))
    for e in entries:
        logger.info("  {}", e)

    async with httpx.AsyncClient(timeout=30) as client:
        # Open the 40-second service window
        start_data = await _hq(client, verify_url, api_key, {"action": "start"})
        logger.info("Service window opened: {}", start_data)

        # Split by mode: idle entries use stable storm windMs so can be queued immediately.
        # Production entries need live weather windMs (weather is session-specific, so
        # done verification uses THIS session's weather, not the agent's pre-computed value).
        idle_entries = [e for e in entries if e["turbineMode"] == "idle"]
        prod_entries  = [e for e in entries if e["turbineMode"] == "production"]

        # Queue weather + all idle unlock codes in one burst so the server processes
        # them in parallel — weather (~25s) and idle codes (~2s each) overlap.
        await _hq(client, verify_url, api_key, {"action": "get", "param": "weather"})
        for e in idle_entries:
            await _hq(client, verify_url, api_key, {
                "action": "unlockCodeGenerator",
                "startDate": e["startDate"],
                "startHour": e["startHour"],
                "windMs": float(e["windMs"]),    # storm windMs is stable across sessions
                "pitchAngle": float(e["pitchAngle"]),
            })

        # Collect results as they complete (sourceFunction distinguishes them).
        # Idle codes arrive in ~2s; weather arrives in ~25s; production code queued after.
        unlock_codes: dict[str, tuple[str, float]] = {}  # "DATE HH:MM:SS" → (code, pitch)
        production_queued = False

        for _ in range(40):   # up to 40s of polling
            await asyncio.sleep(1)
            resp = await _hq(client, verify_url, api_key, {"action": "getResult"})
            resp_code = resp.get("code")

            if resp_code == 11:   # no result yet — keep waiting
                continue
            if isinstance(resp_code, int) and resp_code < 0:
                logger.error("getResult error while collecting: {}", resp)
                return

            src = resp.get("sourceFunction", "")

            if src == "weather":
                live_wind = {f["timestamp"]: float(f["windMs"]) for f in resp.get("forecast", [])}
                logger.info("Live weather received: {} data points", len(live_wind))
                # Now we know session windMs — queue production entries
                for e in prod_entries:
                    wind = live_wind.get(e["datetime"], float(e["windMs"]))
                    logger.info("Production {} live windMs: {} (schedule had: {})",
                                e["datetime"], wind, e["windMs"])
                    await _hq(client, verify_url, api_key, {
                        "action": "unlockCodeGenerator",
                        "startDate": e["startDate"],
                        "startHour": e["startHour"],
                        "windMs": wind,
                        "pitchAngle": float(e["pitchAngle"]),
                    })
                production_queued = True

            elif src == "unlockCodeGenerator":
                signed = resp.get("signedParams", {})
                dt = f"{signed['startDate']} {signed['startHour']}"
                unlock_codes[dt] = (resp["unlockCode"], float(signed["pitchAngle"]))
                logger.info("Unlock code for {}: {}", dt, resp["unlockCode"])

            # Done when every entry has a code (production must have been queued first)
            if production_queued and all(
                f"{e['startDate']} {e['startHour']}" in unlock_codes for e in entries
            ):
                break

        missing = [e["datetime"] for e in entries
                   if f"{e['startDate']} {e['startHour']}" not in unlock_codes]
        if missing:
            logger.error("Missing unlock codes for: {} — aborting", missing)
            return

        # Build and submit bulk config
        configs = {
            e["datetime"]: {
                "pitchAngle": unlock_codes[f"{e['startDate']} {e['startHour']}"][1],
                "turbineMode": e["turbineMode"],
                "unlockCode": unlock_codes[f"{e['startDate']} {e['startHour']}"][0],
            }
            for e in entries
        }
        config_resp = await _hq(client, verify_url, api_key, {"action": "config", "configs": configs})
        logger.info("Config submitted: {}", config_resp)

        if config_resp.get("code", -1) < 0:
            logger.error("Config submission failed — stopping")
            return

        # Turbine validation (async — poll until complete)
        await _hq(client, verify_url, api_key, {"action": "get", "param": "turbinecheck"})
        for _ in range(15):
            await asyncio.sleep(1)
            get_result = await _hq(client, verify_url, api_key, {"action": "getResult"})
            logger.info("Turbinecheck: {}", get_result)
            # 11 = no result yet, 31 = still queued — keep polling
            if get_result.get("code") not in (11, 31):
                break

        done_resp = await _hq(client, verify_url, api_key, {"action": "done"})
        logger.info("Done: {}", done_resp)


class Mission17(BaseMission):
    def get_task_name(self) -> str:
        return "windpower"

    async def run(self) -> None:
        from src.domain.types import AgentStatus
        from src.entry import init_db, init_logging
        from src.entry.standalone import StandaloneAgent
        from src.config import settings

        init_logging()
        await init_db()

        verify_url = f"{settings.aidevs4_headquarters_system_url}/verify"
        api_key = settings.aidevs4_headquarters_api_key

        # ── Preflight: get API docs before any session state is created ───────
        async with httpx.AsyncClient(timeout=30) as client:
            help_data = await _hq(client, verify_url, api_key, {"action": "help"})
        logger.info("API help:\n{}", json.dumps(help_data, indent=2, ensure_ascii=False))

        # ── Phase 1: agent collects and analyzes data ─────────────────────────
        agent = StandaloneAgent("alice")
        logger.info("Starting data-collection phase (session={})", agent.session_id)
        result = await agent.send(AGENT_PROMPT)

        while result.status == AgentStatus.WAITING and result.waiting_for:
            for wait in result.waiting_for:
                question = wait.arguments.get("question", "") if wait.arguments else ""
                logger.info("Agent asks: {}", question)
                answer = input(f"[{wait.tool_name}] {question}\nYour answer: ")
                result = await agent.deliver(wait.call_id, answer)

        logger.info("Agent finished (status={}): {}", result.status, result.output)

        # ── Phase 2: Python code handles time-critical submission ─────────────
        if result.workspace_path is None:
            logger.error("No workspace path returned — cannot locate schedule file")
            return

        schedule_path = result.workspace_path / "outbox" / "windpower_schedule.json"
        if not schedule_path.exists():
            logger.error("Schedule file not found: {}", schedule_path)
            logger.info("Workspace contents:\n{}", "\n".join(str(p) for p in result.workspace_path.rglob("*")))
            return

        await _submit_schedule(schedule_path, verify_url, api_key)
