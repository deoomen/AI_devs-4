from pathlib import Path
from pydantic_settings import BaseSettings


_ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = {
        "env_file": (_ROOT_DIR / ".env", _ROOT_DIR.parent / ".env"),
        "extra": "ignore",
    }

    root_dir: Path = _ROOT_DIR  # Absolute path to the `app/` directory.
    app_name: str = "ai-agent"
    debug: bool = False
    log_level: str = "INFO"

    # Auth
    api_key: str = "change-me"

    # Database
    database_url: str = "sqlite+aiosqlite:///./agent.db"

    # Provider
    openrouter_api_key: str = ""
    openrouter_default_chat_model: str = "openai/gpt-4.1-mini"
    openrouter_default_vision_model: str = "google/gemini-3-flash-preview"
    openrouter_default_audio_model: str = "google/gemini-3-flash-preview"
    openrouter_default_tts_model: str = "google/lyria-3-pro-preview"
    provider_max_retries: int = 3

    # AIDevs Headquarters
    aidevs4_headquarters_api_key: str = ""
    aidevs4_headquarters_system_url: str = ""

    # OKO web panel (mission16)
    oko_panel_url: str = ""
    oko_panel_username: str = ""
    oko_panel_password: str = ""

    # Agent defaults
    agent_default_name: str = "alice"
    agent_default_max_turns: int = 10
    agent_default_rate_limit_rpm: int = 30
    agent_fallback_final_text: str = "No response text returned."
    agent_max_turn_final_text: str = "Reached max turn limit before completion."

    # Workspace
    agent_workspace_dir: str = "workspace"
    agent_cleanup_child_workspace: bool = True

    # Langfuse tracing
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"

    # Template variable whitelist — maps {{PLACEHOLDER}} names to setting field names.
    # Only listed keys are resolved in user messages.
    template_whitelist: dict[str, str] = {
        "AIDEVS4_HEADQUARTERS_API_KEY": "aidevs4_headquarters_api_key",
        "AIDEVS4_HEADQUARTERS_SYSTEM_URL": "aidevs4_headquarters_system_url",
        "OKO_PANEL_URL": "oko_panel_url",
        "OKO_PANEL_USERNAME": "oko_panel_username",
        "OKO_PANEL_PASSWORD": "oko_panel_password",
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
