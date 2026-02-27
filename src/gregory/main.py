"""Gregory - Smart House AI. FastAPI application entry."""

import logging
import sys

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gregory.api.routes import chat, health, users
from gregory.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown."""
    import asyncio

    from gregory.ollama_ensure import ensure_ollama_models

    if getattr(settings, "ollama_ensure_models", False):
        asyncio.create_task(ensure_ollama_models())

    reflection_m = getattr(settings, "heartbeat_reflection_minutes", 0) or 0
    cleanup_m = getattr(settings, "heartbeat_notes_cleanup_minutes", 0) or 0
    if reflection_m > 0 or cleanup_m > 0:
        from gregory.heartbeat import run_heartbeat
        asyncio.create_task(run_heartbeat())

    yield


logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Gregory",
    description="Smart House AI - HTTP API for chat, Home Assistant, Jellyfin, and more",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(users.router)
app.include_router(chat.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root redirect/info."""
    return {
        "name": "Gregory",
        "description": "Smart House AI",
        "docs": "/docs",
        "health": "/health",
    }
