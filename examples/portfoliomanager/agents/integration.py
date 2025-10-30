"""OpenAI Agents SDK integration helpers for local MCP servers (stdio).

This module provides:
  - call_mcp_tool: utility to spawn an MCP server via stdio and call a tool
  - Tool wrappers suitable for registering with OpenAI function tools
  - Tool JSON Schemas used when defining tools for the model
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from sys import executable as PYTHON_EXE
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


BASE_DIR = Path(__file__).resolve().parents[1]


async def call_mcp_tool(server_rel: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call an MCP tool on a server launched via stdio.

    Args:
      server_rel: path relative to examples/portfoliomanager (e.g., "mcp_portfolio_server/server.py")
      tool: tool name to call
      arguments: JSON-serializable dict of tool arguments

    Returns:
      Structured content from the tool call, or empty dict.
    """
    server_path = BASE_DIR / server_rel

    async with stdio_client(
        StdioServerParameters(command=PYTHON_EXE, args=[str(server_path)], env=os.environ.copy())
    ) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, arguments)
            return getattr(result, "structuredContent", {}) or {}


# ---------------------------
# Tool wrappers (async)
# ---------------------------


async def tool_get_portfolio() -> dict[str, Any]:
    return await call_mcp_tool("mcp_portfolio_server/server.py", "get_all_holdings", {})


async def tool_assess_diversification() -> dict[str, Any]:
    return await call_mcp_tool("mcp_portfolio_server/server.py", "assess_diversification", {})


async def tool_assess_risk() -> dict[str, Any]:
    return await call_mcp_tool("mcp_portfolio_server/server.py", "assess_risk", {})


async def tool_fetch_news_for_portfolio(portfolio_snapshot: dict[str, Any] | None = None, max_per_symbol: int = 3) -> dict[str, Any]:
    if portfolio_snapshot is None:
        portfolio_snapshot = await tool_get_portfolio()
    args = {"portfolio_json": json.dumps(portfolio_snapshot), "max_per_symbol": max_per_symbol}
    return await call_mcp_tool("mcp_news_server/server.py", "news_for_portfolio", args)


# ---------------------------
# Tool schemas for OpenAI functions
# ---------------------------


OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_portfolio",
            "description": "Load the current portfolio holdings snapshot (values, P/L, summary).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assess_diversification",
            "description": "Assess diversification: sector weights, HHI concentration, top position weight.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assess_risk",
            "description": "Heuristic risk score (1-10) and risk factors for the portfolio.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_news_for_portfolio",
            "description": "Fetch top headlines relevant to holdings from a news source.",
            "parameters": {
                "type": "object",
                "properties": {
                    "portfolio_snapshot": {"type": "object", "description": "Optional portfolio snapshot; if omitted, it will be loaded via get_portfolio."},
                    "max_per_symbol": {"type": "integer", "default": 3, "minimum": 1, "maximum": 10},
                },
                "required": [],
            },
        },
    },
]


async def dispatch_tool_call(name: str, arguments_json: str) -> dict[str, Any]:
    """Dispatch OpenAI function call to the appropriate async tool wrapper.

    Returns a dict to be serialized as the tool result content.
    """
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        args = {}

    if name == "get_portfolio":
        return await tool_get_portfolio()
    if name == "assess_diversification":
        return await tool_assess_diversification()
    if name == "assess_risk":
        return await tool_assess_risk()
    if name == "fetch_news_for_portfolio":
        return await tool_fetch_news_for_portfolio(
            portfolio_snapshot=args.get("portfolio_snapshot"),
            max_per_symbol=int(args.get("max_per_symbol", 3)),
        )

    return {"error": f"Unknown tool: {name}"}


