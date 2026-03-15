from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    BAD_REQUEST = "BAD_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    AGENT_ERROR = "AGENT_ERROR"
    NOT_WAITING = "NOT_WAITING"


@dataclass
class AppError(Exception):
    message: str
    status_code: int = 400
    code: ErrorCode = ErrorCode.BAD_REQUEST


def error_envelope(error: AppError) -> dict:
    return {"error": {"code": error.code.value, "message": error.message}}
