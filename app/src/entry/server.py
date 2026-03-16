from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from src.api.routes import chat, health
from src.config import settings
from src.db.engine import engine
from src.db.models import Base
from src.db.seed import seed_default_user
from src.errors import AppError, error_envelope
from src.log import setup_logging

setup_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_default_user()
    logger.info("App ready — {}", settings.app_name)
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(health.router)
app.include_router(chat.router)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content=error_envelope(exc))


if __name__ == "__main__":
    uvicorn.run("src.entry.server:app", host="0.0.0.0", port=8000, reload=settings.debug)
