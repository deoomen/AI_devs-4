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

from src.tools.workspace import get_workspace_path
from src.domain.ids import AgentId, SessionId


class SessionWorkspace:
    """Manages a session's directory structure within the workspace.

    All paths stored and returned are relative to the workspace root.
    Use ``resolve()`` to get an absolute path for filesystem operations.
    """

    def __init__(self, session_id: SessionId, session_date: date | None = None):
        d = session_date or date.today()
        self.root = Path(str(d.year)) / f"{d.month:02d}" / f"{d.day:02d}" / f"ses_{session_id.short()}"

    def resolve(self, relative: Path | None = None) -> Path:
        """Resolve a workspace-relative path to absolute. Defaults to session root."""
        base = get_workspace_path()
        return base / (relative or self.root)

    def setup(self) -> None:
        """Create session directory structure."""
        root_abs = self.resolve()
        (root_abs / "attachments").mkdir(parents=True, exist_ok=True)
        (root_abs / "agents").mkdir(parents=True, exist_ok=True)
        plan = root_abs / "plan.md"
        if not plan.exists():
            plan.write_text("", encoding="utf-8")
        logger.info("Session workspace created: {}", self.root)

    def create_agent_dir(self, agent_id: AgentId) -> Path:
        """Create agent subdirectory with inbox/notes/outbox. Returns relative agent root."""
        agent_rel = self.agent_dir(agent_id)
        agent_abs = self.resolve(agent_rel)
        for sub in ("inbox", "notes", "outbox"):
            (agent_abs / sub).mkdir(parents=True, exist_ok=True)
        logger.info("Agent workspace created: {}", agent_rel)
        return agent_rel

    def agent_dir(self, agent_id: AgentId) -> Path:
        """Return agent directory path (relative to workspace root)."""
        return self.root / "agents" / f"agnt_{agent_id.short()}"

    @property
    def agents_dir(self) -> Path:
        return self.root / "agents"

    @property
    def attachments(self) -> Path:
        return self.root / "attachments"

    @property
    def plan(self) -> Path:
        return self.root / "plan.md"
