"""Session-scoped workspace directory management.

Creates and manages the date-based session workspace structure:

    workspaces/{year}/{month}/{day}/ses_{id}/
        plan.md
        attachments/
        agents/
            agnt_{id}/
                inbox/
                notes/
                outbox/

Principles:
    Isolation:     agents live inside sessions — kill session, agents gone.
    Communication: orchestrator routes between inbox/outbox.
    Promotion:     user explicitly moves artifacts to /shared.
"""

from datetime import date
from pathlib import Path

from loguru import logger

from src.config import get_workspace_path


class SessionWorkspace:
    """Manages a session's directory structure within the workspace."""

    def __init__(self, session_id: str, session_date: date | None = None):
        d = session_date or date.today()
        base = get_workspace_path()
        short_id = session_id.replace("-", "")[:8]
        self.root = base / str(d.year) / f"{d.month:02d}" / f"{d.day:02d}" / f"ses_{short_id}"

    def setup(self) -> None:
        """Create session directory structure."""
        (self.root / "attachments").mkdir(parents=True, exist_ok=True)
        (self.root / "agents").mkdir(parents=True, exist_ok=True)
        plan = self.root / "plan.md"
        if not plan.exists():
            plan.write_text("", encoding="utf-8")
        logger.info("Session workspace created: {}", self.root)

    def create_agent_dir(self, agent_id: str) -> Path:
        """Create agent subdirectory with inbox/notes/outbox. Returns agent root."""
        short_id = agent_id.replace("-", "")[:8]
        agent_dir = self.root / "agents" / f"agnt_{short_id}"
        for sub in ("inbox", "notes", "outbox"):
            (agent_dir / sub).mkdir(parents=True, exist_ok=True)
        logger.info("Agent workspace created: {}", agent_dir)
        return agent_dir

    def agent_dir(self, agent_id: str) -> Path:
        """Return agent directory path (without creating it)."""
        short_id = agent_id.replace("-", "")[:8]
        return self.root / "agents" / f"agnt_{short_id}"

    @property
    def attachments(self) -> Path:
        return self.root / "attachments"

    @property
    def plan(self) -> Path:
        return self.root / "plan.md"
