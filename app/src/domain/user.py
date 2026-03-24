from dataclasses import dataclass

from .ids import UserId


@dataclass
class User:
    id: UserId
    email: str
    api_key_hash: str
