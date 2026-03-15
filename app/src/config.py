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

    # Auth
    api_key: str = "change-me"

    # Database
    database_url: str = "sqlite+aiosqlite:///./agent.db"

    # Provider
    openrouter_api_key: str = ""
    openrouter_default_model: str = "openai/gpt-4.1-mini"
    provider_max_retries: int = 3

    # Agent defaults
    agent_default_name: str = "alice"
    agent_max_turns: int = 10
    agent_rate_limit_rpm: int = 30


settings = Settings()
