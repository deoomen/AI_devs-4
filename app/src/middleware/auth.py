import hashlib

from src.domain.user import User
from src.repositories.user import UserRepository


async def authenticate(authorization: str | None, user_repo: UserRepository) -> User | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    return await user_repo.get_by_api_key_hash(key_hash)
