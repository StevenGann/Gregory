"""Gregory - Smart House AI. FastAPI application entry."""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gregory.api.routes import chat, health, users
from gregory.config import get_settings

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Gregory",
    description="Smart House AI - HTTP API for chat, Home Assistant, Jellyfin, and more",
    version="0.1.0",
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
