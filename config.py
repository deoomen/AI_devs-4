import os
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass(frozen=True)
class Config:
    openrouter_api_key: str
    aidevs4_headquarters_api_key: str
    aidevs4_headquarters_system_url: str
    proxy_agent_url: str
    gemini_api_key: str | None = None
    openai_api_key: str | None = None


def load_config() -> Config:
    load_dotenv()
    return Config(
        openrouter_api_key=os.environ["OPENROUTER_API_KEY"],
        aidevs4_headquarters_api_key=os.environ["AIDEVS4_HEADQUARTERS_API_KEY"],
        aidevs4_headquarters_system_url=os.environ["AIDEVS4_HEADQUARTERS_SYSTEM_URL"],
        proxy_agent_url=os.environ.get("PROXY_AGENT_URL"),
        gemini_api_key=os.environ.get("GEMINI_API_KEY"),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )
