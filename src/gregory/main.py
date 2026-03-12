"""Gregory - Smart House AI. FastAPI application entry point.

This module creates the FastAPI application and manages the application
lifespan. On startup it:
  1. Builds the skill registry (Wikipedia, web search, Home Assistant, etc.)
  2. Connects to any configured MCP servers and registers their tools
  3. (Optionally) auto-pulls missing Ollama models in the background
  4. (Optionally) starts the heartbeat background tasks (self-reflection,
     notes cleanup, daily journal summary, monthly memory compression)
  5. (Optionally) reindexes existing journal files into the ChromaDB vector
     store so memory search is available immediately after restart

On shutdown it tears down MCP server connections cleanly.
"""

import logging
import sys

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gregory.api.routes import chat, debug, health, memory, users
from gregory.config import get_settings
from gregory.log_buffer import install_log_handler

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup tasks run before ``yield``, shutdown after.

    The order of startup operations matters:
    - Skills must be registered before the first chat request arrives.
    - MCP connections must be established after the skill registry exists.
    - Heartbeat and memory tasks are non-blocking background tasks; they do
      not delay startup even if they take time.
    """
    import asyncio

    from gregory.ollama_ensure import ensure_ollama_models
    from gregory.skills.loader import build_registry

    # Step 1: Build skill registry (Wikipedia, web search, Home Assistant, etc.)
    # This populates the module-level singleton accessed by chat.py via get_registry().
    registry = build_registry()
    logger.info("[startup] Skill registry initialized")

    # Step 2: Connect MCP servers and register their tools as additional skills.
    # Each tool exposed by an MCP server is wrapped as an MCPSkill and added to
    # the registry so the AI can invoke it via its marker syntax.
    mcp_manager = None
    mcp_server_configs = getattr(settings, "mcp_servers", [])
    if mcp_server_configs:
        from gregory.mcp.client import MCPClientManager
        mcp_manager = MCPClientManager(mcp_server_configs, registry)
        await mcp_manager.connect_all()
        logger.info("[startup] MCP client manager connected")

    # Step 3: (Optional) pull any missing Ollama models in the background.
    # This runs asynchronously so it doesn't block the server from accepting requests.
    if getattr(settings, "ollama_ensure_models", False):
        asyncio.create_task(ensure_ollama_models())

    # Step 4: (Optional) start heartbeat background tasks.
    # Heartbeat tasks only start if at least one interval is configured (non-zero).
    reflection_m = getattr(settings, "heartbeat_reflection_minutes", 0) or 0
    cleanup_m = getattr(settings, "heartbeat_notes_cleanup_minutes", 0) or 0
    summary_m = getattr(settings, "heartbeat_daily_summary_minutes", 0) or 0
    compression_m = getattr(settings, "heartbeat_memory_compression_minutes", 0) or 0
    if reflection_m > 0 or cleanup_m > 0 or summary_m > 0 or compression_m > 0:
        from gregory.heartbeat import run_heartbeat
        asyncio.create_task(run_heartbeat())

    # Step 5: (Optional) reindex journal files into ChromaDB on startup.
    # Uses upsert so it is safe to run on every restart (idempotent).
    # Runs as a background task to avoid blocking the server.
    if getattr(settings, "memory_enabled", False):
        from gregory.memory.service import startup_reindex
        asyncio.create_task(startup_reindex(), name="memory-reindex")
        logger.info("[startup] Memory system enabled; reindexing journal files in background")

    yield  # Application runs; requests are handled here

    # Shutdown: cancel all MCP background session tasks cleanly
    if mcp_manager:
        await mcp_manager.close_all()


logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
install_log_handler()
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
app.include_router(memory.router)
app.include_router(debug.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root redirect/info."""
    return {
        "name": "Gregory",
        "description": "Smart House AI",
        "docs": "/docs",
        "health": "/health",
    }
