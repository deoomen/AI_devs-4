from dataclasses import dataclass


@dataclass
class AppError(Exception):
    message: str
    status_code: int = 400
    code: str = "BAD_REQUEST"


def error_envelope(error: AppError) -> dict:
    return {"error": {"code": error.code, "message": error.message}}
