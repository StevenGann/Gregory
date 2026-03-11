"""MCPSkill — wraps a single MCP server tool as a Gregory Skill."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from gregory.skills.base import SkillResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _make_marker_pattern(server_name: str, tool_name: str) -> re.Pattern:
    """Build the marker pattern for [MCP:server/tool: {json}]."""
    # Escape dots/special chars in server and tool names
    sn = re.escape(server_name)
    tn = re.escape(tool_name)
    return re.compile(
        rf"\[MCP:{sn}/{tn}:\s*(\{{[^]]*\}})\]",
        re.IGNORECASE | re.DOTALL,
    )


def _build_instruction(server_name: str, tool_name: str, description: str, schema: dict) -> str:
    """Generate a system-prompt instruction block for an MCP tool."""
    props = schema.get("properties", {})
    required = schema.get("required", [])
    param_lines: list[str] = []
    for pname, pdef in props.items():
        ptype = pdef.get("type", "string")
        pdesc = pdef.get("description", "")
        req_flag = " (required)" if pname in required else ""
        param_lines.append(f"  - `{pname}` ({ptype}{req_flag}): {pdesc}")

    params_text = "\n".join(param_lines) if param_lines else "  (no parameters)"
    return (
        f"### MCP tool: {server_name}/{tool_name}\n\n"
        f"{description}\n\n"
        f"**Usage:** `[MCP:{server_name}/{tool_name}: {{\"param\": \"value\"}}]`\n\n"
        f"**Parameters:**\n{params_text}"
    )


class MCPSkill:
    """A Gregory skill backed by a remote MCP server tool.

    Instances are created dynamically by MCPClientManager when tools are
    discovered from a connected server.
    """

    def __init__(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        input_schema: dict,
        call_tool_fn,  # async callable: (tool_name, args) -> mcp CallToolResult
        enabled: bool = True,
    ) -> None:
        self.server_name = server_name
        self.tool_name = tool_name
        self.name = f"{server_name}/{tool_name}"
        self.marker_pattern = _make_marker_pattern(server_name, tool_name)
        self.instruction = _build_instruction(server_name, tool_name, description, input_schema)
        self.enabled = enabled
        self._call_tool = call_tool_fn
        self._input_schema = input_schema

    async def execute(self, query: str) -> SkillResult:
        """Parse JSON args from *query* and call the MCP tool."""
        try:
            args: dict[str, Any] = json.loads(query) if query.strip() else {}
        except json.JSONDecodeError as e:
            return SkillResult(
                skill_name=self.name,
                query=query,
                content=f"## MCP {self.name}\n\nInvalid JSON args: {e}",
                success=False,
                error=str(e),
            )

        try:
            result = await self._call_tool(self.tool_name, args)
        except Exception as e:
            logger.warning("[mcp_skill] Tool %r call failed: %s", self.name, e)
            return SkillResult(
                skill_name=self.name,
                query=query,
                content=f"## MCP {self.name}\n\nTool call failed: {e}",
                success=False,
                error=str(e),
            )

        # Extract text content from MCP result
        content_parts: list[str] = []
        for item in getattr(result, "content", []):
            if hasattr(item, "text"):
                content_parts.append(item.text)
            elif isinstance(item, dict) and "text" in item:
                content_parts.append(item["text"])

        content_text = "\n".join(content_parts) if content_parts else str(result)
        is_error = getattr(result, "isError", False)

        return SkillResult(
            skill_name=self.name,
            query=query,
            content=f"## MCP {self.name}\n\n{content_text}",
            success=not is_error,
            error=content_text if is_error else "",
        )
