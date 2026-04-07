import base64
import json
import re
import shutil
import sys
from pathlib import Path

import httpx
from loguru import logger

from missions.base_mission import BaseMission

# Add app/ to sys.path so we can import the agent runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

# ── Paths ───────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SHARED_DIR = _PROJECT_ROOT / "app" / "workspace" / "shared" / "mission21"
LISTEN_DATA_DIR = SHARED_DIR / "listen_data"
INTERESTING_DIR = SHARED_DIR / "interesting"

# ── Constants ───────────────────────────────────────────────────────────────

TASK = "radiomonitoring"
MAX_LISTEN_CALLS = 150  # safety cap

MIME_TO_EXT: dict[str, str] = {
    "application/json": ".json",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "text/plain": ".txt",
    "text/html": ".html",
    "text/xml": ".xml",
    "text/csv": ".csv",
    "application/xml": ".xml",
    "application/csv": ".csv",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "application/pdf": ".pdf",
    "application/octet-stream": ".bin",
}

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# Patterns that flag a text file as interesting
_INTERESTING_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"syjon", re.IGNORECASE), "contains 'Syjon'"),
    (re.compile(r"magazyn", re.IGNORECASE), "contains 'magazyn' (warehouse)"),
    (re.compile(r"powierzchnia", re.IGNORECASE), "contains 'powierzchnia' (area)"),
    (re.compile(r"\d+[.,]\d+\s*(km|ha|hektar)", re.IGNORECASE), "contains area measurement"),
    (re.compile(r"(?:tel\.?|telefon|kontakt|phone)[^\d\n]{0,10}\+?[\d][\d\s\-]{7,}", re.IGNORECASE), "contains phone ref"),
    (re.compile(r"\b\d{9}\b"), "contains 9-digit number (possible phone)"),
    (re.compile(r"miasto|miejscowo[śs][ćc]|lokalizacja|wsp[oó][lł]rz", re.IGNORECASE), "contains city/location ref"),
]

# ── Agent prompt ─────────────────────────────────────────────────────────────

USER_MESSAGE = """\
Complete the "radiomonitoring" mission. Intercepted radio data has already been collected and \
pre-filtered. Your job is to analyze it, extract four specific values about the hidden survivor \
city known as "Syjon", and transmit a final report to headquarters.

## Data in shared/

- `shared/mission21/notes/` — **check this first**: may contain findings and partial results from previous runs
- `shared/mission21/interesting/` — priority files, pre-filtered as most likely to contain useful data
- `shared/mission21/interesting.txt` — index listing each interesting filename and why it was flagged
- `shared/mission21/listen_data/` — the full raw dataset (all intercepts)
- for each binary file (image, audio, etc.) a `.txt` description with the same base filename may already exist — always check before delegating

## What you must extract

| Field | Description |
|---|---|
| `cityName` | Real name of the city the resistance calls "Syjon" |
| `cityArea` | City area in km², as a string with exactly 2 decimal places e.g. `"12.34"` |
| `warehousesCount` | Number of warehouses (magazyny) — must be an integer |
| `phoneNumber` | Phone number of the city contact person |

**Important:** the answers are rarely stated directly. Intercepts are fragments — different files may each carry a piece of the puzzle. Use think to reason across multiple sources, connect indirect clues, and draw conclusions. A file mentioning a city name, another mentioning warehouse count, and an image showing a map may all be needed together.

## Strategy

### Phase 0 — Resume check
1. List `shared/mission21/notes/` and read any existing files there. If previous findings are present, skip straight to whichever phase is still incomplete.

### Phase 1 — Priority files
2. Read `shared/mission21/interesting.txt` to see the list and flags.
3. For each interesting file, convert it to text first, then **read and understand the full content**:
   Before delegating, **check if `<filename>.txt` already exists** in `shared/mission21/interesting/` — if so, read it directly and skip delegation.
   Use the file extension as a hint when choosing which specialist to delegate to:
   - `.txt` / `.json` / `.csv` / `.xml` → read_file directly (no delegation needed)
   - `.html` → a specialist that can parse and extract content from web/HTML documents
   - images (`.png`, `.jpg`, `.gif`, `.webp`, etc.) → a specialist with image analysis capability; ask for a detailed description of ALL visible text, numbers, labels, symbols, layout, and any countable elements
   - audio (`.mp3`, `.wav`, etc.) → a specialist capable of transcribing audio files; ask for a full transcription
   - `.pdf` or other document formats → a specialist suited to structured document extraction
   - any other unknown binary → use file metadata (extension, size) to pick the most fitting specialist
   In all cases: save the specialist's output as `shared/mission21/interesting/<filename>.txt`, then read that `.txt`.
4. After reading ALL priority files, use think to deeply reason across everything collected:
   - What does each piece of information tell you, directly or indirectly?
   - Some fields will NOT be stated explicitly — they must be inferred.
   - Cross-reference across files: a name in one file, a number in another, a map in a third may together answer one question.
   - Write your full reasoning and current best answers to `shared/mission21/notes/analysis.md`.

### Phase 2 — Expand search (only if fields are still missing after deep analysis)
5. Only after exhausting reasoning on existing data, expand the search:
   - Read remaining files in `shared/mission21/listen_data/` that weren't in the priority list
   - For non-text files, delegate description/transcription and save as `<filename>.txt` alongside the original
   - After each new file read, use think to re-reason — do not just grep for keywords and give up if no direct match is found

### Phase 3 — Transmit
6. Once all 4 fields are confirmed, use think to verify consistency.
7. Send to headquarters via aidevs_headquarters:
   - task: `"radiomonitoring"`
   - answer: `{"action": "transmit", "cityName": "...", "cityArea": "12.34", "warehousesCount": 321, "phoneNumber": "..."}`
   - `cityArea` MUST be a string like "12.34" (exactly 2 decimal places, proper rounding)
   - `warehousesCount` MUST be an integer (not a string)

### Phase 4 — Iterate on HQ feedback
8. If the transmit fails or returns an error:
   - The error message may hint at which field is wrong
   - Only then: list all files in `shared/mission21/listen_data/` and search for additional evidence
   - Fix the specific field and re-transmit
9. Repeat until you receive a flag ({FLG:...}).

## Rules
- Save all intermediate findings to `shared/mission21/notes/` — this persists across re-runs. Do NOT use your local notes/ for mission findings.
- **Search is a last resort, not a strategy.** Grep and keyword search only find what is explicitly written. Most answers require reading, understanding, and reasoning — not just matching strings.
- Do NOT guess any value — all 4 fields must come from the intercepted data, but they may require inference and cross-referencing to derive.
- `cityArea` format is critical: string, exactly 2 decimal places, real mathematical rounding.
- When a specialist describes a non-text file, always save the result as `<original_filename>.txt` in the same directory, then read that `.txt` for analysis — this creates a searchable text trail for Phase 2.
- Always read the full result file from inbox/agnt_{id}/ after any delegation.
"""

# ── Mission class ─────────────────────────────────────────────────────────────


class Mission21(BaseMission):
    def get_task_name(self) -> str:
        return TASK

    async def run(self) -> None:
        await self._collect_data()
        self._filter_and_index()
        await self._run_agent()

    # ── Phase 1: Collect ─────────────────────────────────────────────────────

    async def _collect_data(self) -> None:
        LISTEN_DATA_DIR.mkdir(parents=True, exist_ok=True)

        existing = [f for f in LISTEN_DATA_DIR.iterdir() if f.is_file()]
        if existing:
            logger.info("listen_data already populated ({} files) — skipping collection", len(existing))
            return

        api_url = self.config.aidevs4_headquarters_system_url + "/verify"
        api_key = self.config.aidevs4_headquarters_api_key

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Start session
            logger.info("Starting radiomonitoring session…")
            resp = await client.post(api_url, json={
                "apikey": api_key,
                "task": TASK,
                "answer": {"action": "start"},
            })
            data = resp.json()
            logger.info("start → code={} msg={}", data.get("code"), data.get("message"))

            # Listen loop
            for i in range(MAX_LISTEN_CALLS):
                resp = await client.post(api_url, json={
                    "apikey": api_key,
                    "task": TASK,
                    "answer": {"action": "listen"},
                })
                data = resp.json()
                code = data.get("code")
                msg = data.get("message", "")
                logger.info("listen #{:03d}  code={}  msg={}", i, code, msg)

                if code != 100:
                    logger.info("Session closed by server (code={}) — {}", code, msg)
                    break

                self._save_message(i, data)
            else:
                logger.warning("Reached MAX_LISTEN_CALLS ({}) without server close signal", MAX_LISTEN_CALLS)

    def _save_message(self, index: int, data: dict) -> None:
        base = f"msg_{index:04d}"

        if "transcription" in data:
            path = LISTEN_DATA_DIR / f"{base}.txt"
            path.write_text(data["transcription"], encoding="utf-8")
            logger.debug("  → {}", path.name)

        elif "attachment" in data:
            mime = data.get("meta", "application/octet-stream")
            ext = MIME_TO_EXT.get(mime, ".bin")
            path = LISTEN_DATA_DIR / f"{base}{ext}"
            try:
                raw = base64.b64decode(data["attachment"])
                path.write_bytes(raw)
                logger.debug("  → {} ({} bytes, {})", path.name, len(raw), mime)
            except (ValueError, OSError) as exc:
                logger.warning("  Base64 decode failed for #{}: {}", index, exc)
                fallback = LISTEN_DATA_DIR / f"{base}.b64.txt"
                fallback.write_text(data["attachment"], encoding="utf-8")

        else:
            # Noise / metadata-only response
            path = LISTEN_DATA_DIR / f"{base}.noise.json"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.debug("  → {} (noise)", path.name)

    # ── Phase 2: Filter ──────────────────────────────────────────────────────

    def _filter_and_index(self) -> None:
        INTERESTING_DIR.mkdir(parents=True, exist_ok=True)

        if any(INTERESTING_DIR.iterdir()):
            logger.info("interesting/ already populated — skipping filter")
            return

        interesting: list[tuple[str, list[str]]] = []

        for fpath in sorted(LISTEN_DATA_DIR.iterdir()):
            if not fpath.is_file():
                continue
            if fpath.name.endswith(".noise.json"):
                continue

            reasons = self._check_interesting(fpath)
            if reasons:
                interesting.append((fpath.name, reasons))
                shutil.copy2(fpath, INTERESTING_DIR / fpath.name)

        # Write index file
        lines = [
            "# Interesting files from radiomonitoring intercepts",
            "# Format: filename | reasons flagged by pre-filter",
            "",
        ]
        for fname, reasons in interesting:
            lines.append(f"{fname} | {', '.join(reasons)}")

        index_path = SHARED_DIR / "interesting.txt"
        index_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Pre-filter: {} interesting files → {}", len(interesting), index_path)

    def _check_interesting(self, fpath: Path) -> list[str]:
        suffix = fpath.suffix.lower()

        # Image files → always flag for dave
        if suffix in IMAGE_SUFFIXES:
            return ["image file (needs visual analysis)"]

        # Other non-text binaries
        if suffix in {".bin", ".mp3", ".wav", ".pdf"}:
            return [f"binary file ({suffix})"]

        # Read text content
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []

        # For JSON, normalise to a flat string for pattern matching
        if suffix == ".json":
            try:
                parsed = json.loads(content)
                content = json.dumps(parsed, ensure_ascii=False)
            except (ValueError, json.JSONDecodeError):
                pass

        reasons = []
        for pattern, reason in _INTERESTING_PATTERNS:
            if pattern.search(content):
                reasons.append(reason)

        return reasons

    # ── Phase 3: Run agent ────────────────────────────────────────────────────

    async def _run_agent(self) -> None:
        from src.domain.types import AgentStatus
        from src.entry import init_db, init_logging
        from src.entry.standalone import StandaloneAgent

        init_logging()
        await init_db()

        agent = StandaloneAgent("alice")
        logger.info("Launching alice for '{}' mission (session={})", TASK, agent.session_id)
        result = await agent.send(USER_MESSAGE)

        while result.status == AgentStatus.WAITING and result.waiting_for:
            for wait in result.waiting_for:
                logger.info("Agent asks: {}", result.output)
                answer = input(f"[{wait.tool_name}] Your answer: ")
                result = await agent.deliver(wait.call_id, answer)

        logger.info("Agent finished (status={}):\n{}", result.status, result.output)
