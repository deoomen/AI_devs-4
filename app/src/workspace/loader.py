import yaml
from loguru import logger

from src.config import ROOT_DIR, settings
from src.domain.agent import AgentConfig

AGENTS_DEFINITIONS_DIR = ROOT_DIR / "src" / "workspace" / "agents"


def list_agent_names() -> list[str]:
    """Return names of all available agent configs (excluding the caller)."""
    return sorted(
        p.stem.removesuffix(".agent")
        for p in AGENTS_DEFINITIONS_DIR.glob("*.agent.md")
    )


def load_agent_config(name: str) -> AgentConfig | None:
    path = AGENTS_DEFINITIONS_DIR / f"{name}.agent.md"
    if not path.exists():
        logger.warning("Agent file not found: {}", path)
        return None

    text = path.read_text()
    if not text.startswith("---"):
        logger.warning("Agent file missing YAML frontmatter: {}", path)
        return None

    parts = text.split("---", 2)
    if len(parts) < 3:
        logger.warning("Agent file malformed frontmatter: {}", path)
        return None

    frontmatter = yaml.safe_load(parts[1])
    body = parts[2].strip()

    return AgentConfig(
        name=frontmatter.get("name", name),
        model=frontmatter.get("model", ""),
        system_prompt=body,
        description=frontmatter.get("description", ""),
        tools=frontmatter.get("tools", []),
        max_turns=frontmatter.get("max_turns", settings.agent_default_max_turns),
    )
