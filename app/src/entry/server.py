"""FastAPI application definition.

Not meant to be run directly — use `python main.py server`.
Can also be loaded by uvicorn: `uvicorn src.entry.server:app`.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from src.api.routes import chat, health
from src.config import settings
from src.db.engine import engine
from src.db.models import Base
from src.db.seed import seed_default_user
from src.errors import AppError, error_envelope
from src.tracing.subscriber import shutdown_tracing


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_default_user()
    logger.info("App ready — {}", settings.app_name)
    yield
    await engine.dispose()
    shutdown_tracing()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(health.router)
app.include_router(chat.router)


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content=error_envelope(exc))
