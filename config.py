import os
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass(frozen=True)
class Config:
    headquarters_api_key: str
    headquarters_system_url: str
    openrouter_api_key: str


def load_config() -> Config:
    load_dotenv()
    return Config(
        headquarters_api_key=os.environ["HEADQUARTERS_API_KEY"],
        headquarters_system_url=os.environ["HEADQUARTERS_SYSTEM_URL"],
        openrouter_api_key=os.environ["OPENROUTER_API_KEY"],
    )
