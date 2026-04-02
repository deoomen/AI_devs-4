from loguru import logger
import sys
from pathlib import Path

from missions.base_mission import BaseMission

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "app"))

USER_MESSAGE = """\
Complete the "filesystem" mission. Natan's trade notes are in `shared/natan_notes/`.

## Your job

Build a structured knowledge base from Natan's trade notes and submit it to the filesystem API.
The knowledge base persists in `shared/kb/` across runs — always check what is already there
before doing any work, so re-runs iterate on existing results rather than starting from scratch.

## Step 0 — Check for existing knowledge base

List `shared/kb/miasta/`, `shared/kb/osoby/`, `shared/kb/towary/` in parallel.

**If all three directories exist and contain files:**
- Read the existing notes
- Skip to Step 4 (Verify) to check for gaps or issues
- Then go straight to Step 5 (Submit)

**If `shared/kb/` is empty or missing:**
- Continue with Step 1 from scratch

**If HQ rejects:**
- The KB is incomplete — an entity was missed during the original analysis
- Go back to Step 2: re-read all Natan's notes, find the missing entity, delegate only the missing note to Grace, copy it to `shared/kb/`, then resubmit
- Do not rebuild the entire KB — add only what is missing

## Step 1 — Orient

Read `shared/knowledge_map.md` first. It explains the knowledge base structure,
where notes are stored (`shared/kb/`), and the naming rules.

## Step 2 — Read and analyse Natan's notes

List `shared/natan_notes/` and read all files in parallel.

Use `think` to extract every entity:
- **Cities**: display name + ASCII filename. For each: what goods does it NEED (demand + quantity)? What goods does it OFFER (supply)?
- **People**: all mentions of a person across ALL notes — full name, which city they manage
- **Goods offered**: good name (singular nominative, ASCII), which city offers it

### Person name reconciliation (mandatory before proceeding)

Names may appear partially across different notes — a first note may mention only "Jan"
and a later note may reveal "Jan Kowalski". You must reconcile across all notes before
creating any person entry:

1. Collect every person mention from every note (first name only, full name, nickname, etc.)
2. Use `think` to group mentions that refer to the same person — match by first name,
   context (same city, same role), or any other clue in the notes
3. For each person, use the most complete name found — always prefer `firstname lastname`
   over firstname alone
4. If after reading all notes a person still has only a first name with no last name found
   anywhere, flag them explicitly in `notes/entities.md` as `[INCOMPLETE]` — do not create
   their note until you have both parts

Save the full reconciled list to `notes/entities.md` before proceeding.
Format each person as: `{firstname} {lastname} → {ascii_filename} → manages: {city}`

## Step 3 — Delegate note creation to Grace

For each entity, delegate to the `grace` agent. Pass Grace a clear, self-contained message with:
- The entity data
- The template directory: `shared/templates/`

Grace will discover the templates herself, pick the right one, and write the note to her outbox.
She also writes `outbox/result.md` with the filename she used.

Example message for a city:
```
Create a knowledge base note for the following entity:

Type: city
Display name: Warszawa
Filename (ASCII, lowercase): warszawa
Needs (goods to buy, quantities as numbers): {"chleb": 10, "woda": 50}
Offers (goods for sale): chleb, woda

Templates directory: shared/templates/
```

Example for a person:
```
Create a knowledge base note for the following entity:

Type: person
Full name: Jan Kowalski
Manages city: Warszawa (filename: warszawa)

Templates directory: shared/templates/
```

Example for an offered good:
```
Create a knowledge base note for the following entity:

Type: good
Name (singular nominative, ASCII, lowercase): koparka
Offered by city: Warszawa (filename: warszawa)

Templates directory: shared/templates/
```

After each delegation, read `inbox/agnt_{id}/result.md` to learn the filename Grace used.
Then promote the note to `shared/kb/` using `copy_file`:
- `src`: `inbox/agnt_{id}/{filename}`
- `dest`: `shared/kb/{category}/{filename}`

Determine the correct category from the entity type:
- city   → `shared/kb/miasta/{filename}`
- person → `shared/kb/osoby/{filename}`
- good   → `shared/kb/towary/{filename}`

**Note**: `delegate` is always sequential. Extract and plan all entities first, then delegate one by one.

## Step 4 — Verify

After all delegations and copies, list `shared/kb/miasta/`, `shared/kb/osoby/`, `shared/kb/towary/`.

Use `think` to verify ALL of the following before proceeding:
- Every expected entity has a note
- No duplicate filenames within any directory
- Every file in `osoby/` has BOTH first and last name: format must be `{firstname}_{lastname}` — a single name alone is not valid
- No filename has a file extension (no `.md`, `.json`, `.txt` or any other suffix)

Fix any issues with `write_file` before submitting.

## Step 5 — Submit to the filesystem API

List and read all notes from `shared/kb/` in parallel.

**`reset` and `done` cannot be included in a batch — send them as separate individual requests.**

Execute in this exact order:

1. Send `reset` alone first:
```json
{"action": "reset"}
```

2. Send the batch with dirs and files:
```json
[
  {"action": "createDir", "path": "/miasta"},
  {"action": "createDir", "path": "/osoby"},
  {"action": "createDir", "path": "/towary"},
  {"action": "createFile", "path": "/miasta/{nazwa}", "content": "..."},
  {"action": "createFile", "path": "/osoby/{firstname}_{lastname}", "content": "..."},
  {"action": "createFile", "path": "/towary/{towar}", "content": "..."}
]
```

3. Analyse the batch response and iterate if needed (see below).

4. Send `done` alone when the structure is correct:
```json
{"action": "done"}
```

### Analyse the response and iterate

Read the response carefully and act based on the error type:

- **Wrong content / wrong format / wrong filename** → fix the affected note in `shared/kb/` with `write_file`, send `reset`, resend the full batch
- **Count mismatch (expected N, actual M)** → the KB is missing entities; go back to Step 2, re-read Natan's notes, find what was missed, delegate only the missing note(s) to Grace, copy to `shared/kb/`, then send `reset` and resend the full batch
- **Accepted** → send `done`

Do not include `reset` or `done` in the batch array.

## Naming rules (reminder)

- No Polish characters in filenames or JSON keys (ą→a, ę→e, ó→o, ś→s, ł→l, ź→z, ż→z, ć→c, ń→n)
- All filenames must be lowercase
- No file extensions in filenames (no `.md`, `.json`, `.txt`, etc.)
- Goods: singular nominative (koparka not koparki)
- Persons: `{firstname}_{lastname}` — both parts mandatory, all lowercase
- Cities: lowercase ASCII
- JSON quantity values must be numbers, not strings

Task name for the API: **filesystem**
"""


class Mission19(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "filesystem"

    async def run(self) -> None:
        from src.domain.types import AgentStatus
        from src.entry import init_db, init_logging
        from src.entry.standalone import StandaloneAgent

        init_logging()
        # from src.tools.native.aidevs_headquarters import _execute
        # await _execute({
        #     "task": "filesystem",
        #     "answer": {
        #         "action": "done",
        #     }
        # })
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
