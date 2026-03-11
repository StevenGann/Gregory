"""Gregory MCP (Model Context Protocol) client support.

Connects Gregory to external MCP servers and exposes their tools as
first-class skills in the skill registry.
"""

from gregory.mcp.client import MCPClientManager

__all__ = ["MCPClientManager"]
