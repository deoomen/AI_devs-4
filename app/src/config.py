from pathlib import Path
from pydantic_settings import BaseSettings


_app_dir = Path(__file__).resolve().parent.parent
_project_root = _app_dir.parent


class Settings(BaseSettings):
    model_config = {
        "env_file": (_app_dir / ".env", _project_root / ".env"),
        "extra": "ignore",
    }

    app_name: str = "ai-agent"
    debug: bool = False
    log_level: str = "INFO"

    # Auth
    api_key: str = "change-me"

    # Database
    database_url: str = "sqlite+aiosqlite:///./agent.db"

    # Provider
    openrouter_api_key: str = ""
    openrouter_default_model: str = "openai/gpt-4.1-mini"
    provider_max_retries: int = 3

    # AIDevs Headquarters
    aidevs4_headquarters_api_key: str = ""
    aidevs4_headquarters_url: str = "***REMOVED***"

    # Agent defaults
    agent_default_name: str = "alice"
    agent_max_turns: int = 10
    agent_rate_limit_rpm: int = 30

    # Workspace
    agent_workspace_dir: str = "workspace"

    # Template variable whitelist — maps {{PLACEHOLDER}} names to setting field names.
    # Only listed keys are resolved in user messages.
    template_whitelist: dict[str, str] = {
        "AIDEVS4_HEADQUARTERS_API_KEY": "aidevs4_headquarters_api_key",
        "AIDEVS4_HEADQUARTERS_SYSTEM_URL": "aidevs4_headquarters_url",
    }

    def get_template_vars(self) -> dict[str, str]:
        """Resolve whitelisted placeholders to their current values."""
        result = {}
        for placeholder, field in self.template_whitelist.items():
            value = getattr(self, field, None)
            if value is not None:
                result[placeholder] = str(value)
        return result


settings = Settings()


def get_workspace_path() -> Path:
    """Resolve the agent workspace data directory (created on first call)."""
    path = (_app_dir / settings.agent_workspace_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path
