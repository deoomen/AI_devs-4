from pathlib import Path

import yaml
from loguru import logger

from src.domain.agent import AgentConfig

AGENTS_DEFINITIONS_DIR = Path(__file__).resolve().parent / "agents"


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
        tools=frontmatter.get("tools", []),
        max_turns=frontmatter.get("max_turns", 10),
    )
