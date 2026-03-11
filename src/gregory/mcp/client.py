"""MCPClientManager — connects Gregory to external MCP servers.

On startup, connects to each configured MCP server, discovers its available
tools, wraps each as an MCPSkill, and registers them into the skill registry.

Supports stdio and SSE/HTTP transports.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class MCPClientManager:
    """Manages connections to one or more MCP servers.

    Usage (in main.py lifespan)::

        manager = MCPClientManager(settings.mcp_servers, registry)
        await manager.connect_all()
        yield
        await manager.close_all()
    """

    def __init__(self, server_configs: list, registry) -> None:
        """
        Args:
            server_configs: list of MCPServerConfig objects from settings.
            registry: SkillRegistry instance to register discovered tools into.
        """
        self._configs = server_configs
        self._registry = registry
        # Keep references to open contexts for cleanup
        self._sessions: list[Any] = []

    async def connect_all(self) -> None:
        """Connect to all enabled MCP servers and register their tools."""
        for cfg in self._configs:
            if not cfg.enabled:
                logger.info("[mcp] Skipping disabled server: %s", cfg.name)
                continue
            try:
                await self._connect_server(cfg)
            except Exception as e:
                logger.warning("[mcp] Failed to connect to server %r: %s", cfg.name, e)

    async def _connect_server(self, cfg) -> None:
        """Connect to a single MCP server and register its tools."""
        try:
            from mcp import ClientSession
            from mcp.client.stdio import StdioServerParameters, stdio_client
            from mcp.client.sse import sse_client
        except ImportError:
            logger.error(
                "[mcp] 'mcp' package not installed. Install with: pip install mcp>=1.0.0"
            )
            return

        transport = cfg.transport.lower()

        if transport == "stdio":
            if not cfg.command:
                logger.warning("[mcp] Server %r has no command configured", cfg.name)
                return
            await self._connect_stdio(cfg)

        elif transport in ("sse", "http"):
            if not cfg.url:
                logger.warning("[mcp] Server %r has no url configured", cfg.name)
                return
            await self._connect_sse(cfg)

        else:
            logger.warning("[mcp] Unknown transport %r for server %r", transport, cfg.name)

    async def _connect_stdio(self, cfg) -> None:
        """Connect via stdio transport (for local MCP servers started as subprocesses)."""
        try:
            from mcp import ClientSession
            from mcp.client.stdio import StdioServerParameters, stdio_client
        except ImportError:
            return

        params = StdioServerParameters(
            command=cfg.command[0],
            args=cfg.command[1:],
            env=None,
        )

        # stdio_client is an async context manager; we enter it and keep it open.
        # We store a background task that holds the connection alive.
        ready = asyncio.Event()
        tools_registered: list[dict] = []

        async def _run_session(read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                tools = tools_result.tools if hasattr(tools_result, "tools") else []
                self._register_tools(cfg.name, tools, session)
                tools_registered.extend([{"name": t.name} for t in tools])
                ready.set()
                # Keep the session alive until shutdown
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    pass

        async def _connect():
            async with stdio_client(params) as (read, write):
                await _run_session(read, write)

        task = asyncio.create_task(_connect())
        self._sessions.append(task)

        try:
            await asyncio.wait_for(ready.wait(), timeout=30.0)
            logger.info(
                "[mcp] Connected to %r via stdio, registered %d tools",
                cfg.name,
                len(tools_registered),
            )
        except asyncio.TimeoutError:
            logger.warning("[mcp] Timeout waiting for server %r to initialize", cfg.name)
            task.cancel()

    async def _connect_sse(self, cfg) -> None:
        """Connect via SSE/HTTP transport."""
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
        except ImportError:
            return

        ready = asyncio.Event()
        tools_registered: list[dict] = []

        async def _run_session(read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                tools = tools_result.tools if hasattr(tools_result, "tools") else []
                self._register_tools(cfg.name, tools, session)
                tools_registered.extend([{"name": t.name} for t in tools])
                ready.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    pass

        async def _connect():
            async with sse_client(cfg.url) as (read, write):
                await _run_session(read, write)

        task = asyncio.create_task(_connect())
        self._sessions.append(task)

        try:
            await asyncio.wait_for(ready.wait(), timeout=30.0)
            logger.info(
                "[mcp] Connected to %r via SSE at %s, registered %d tools",
                cfg.name,
                cfg.url,
                len(tools_registered),
            )
        except asyncio.TimeoutError:
            logger.warning("[mcp] Timeout waiting for SSE server %r at %s", cfg.name, cfg.url)
            task.cancel()

    def _register_tools(self, server_name: str, tools: list, session) -> None:
        """Wrap MCP tools as MCPSkill instances and register them in the skill registry."""
        from gregory.mcp.skill import MCPSkill

        for tool in tools:
            tool_name = tool.name
            description = getattr(tool, "description", "") or ""
            input_schema = {}
            if hasattr(tool, "inputSchema"):
                raw = tool.inputSchema
                input_schema = raw if isinstance(raw, dict) else {}

            # Capture session in closure for the call function
            captured_session = session

            async def _call_tool(tn, args, _session=captured_session):
                return await _session.call_tool(tn, args)

            skill = MCPSkill(
                server_name=server_name,
                tool_name=tool_name,
                description=description,
                input_schema=input_schema,
                call_tool_fn=_call_tool,
                enabled=True,
            )
            self._registry.register(skill)
            logger.debug("[mcp] Registered tool %r from server %r", tool_name, server_name)

    async def close_all(self) -> None:
        """Cancel all background session tasks."""
        for task in self._sessions:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        self._sessions.clear()
        logger.info("[mcp] All MCP sessions closed")
