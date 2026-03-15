from dataclasses import dataclass


@dataclass
class User:
    id: str
    email: str
    api_key_hash: str
