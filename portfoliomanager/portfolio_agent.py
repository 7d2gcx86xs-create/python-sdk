"""Portfolio Manager Agent using OpenAI Agent SDK with MCP.

This script provides an interactive command-line interface to chat with
a portfolio manager assistant. It uses the OpenAI Assistants API to create
and manage the assistant, conversation threads, and runs.

This client follows the "Custom UX" guide from the OpenAI documentation:
https://developers.openai.com/apps-sdk/build/custom-ux

Usage:
  uv run python examples/portfoliomanager/portfolio_agent.py

Requires OPENAI_API_KEY in the environment or a .env file.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from sys import executable as PYTHON_EXE


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# System prompt for the assistant
SYSTEM_PROMPT = (
    "You are a portfolio assistant. You have tools to read a local MCP portfolio server "
    "and a news server. Use tools when asked about current portfolio data or headlines."
)

BASE_DIR = Path(__file__).resolve().parent

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


async def dispatch_tool_call(tool_call) -> dict[str, Any]:
    """Dispatch OpenAI function call to the appropriate async tool wrapper.

    Returns a dict to be serialized as the tool result content.
    """
    name = tool_call.function.name
    arguments_json = tool_call.function.arguments
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


async def main():
    """Main interactive loop for the portfolio manager agent."""
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")

    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not set in the environment or .env file.")

    client = OpenAI()

    # For production use, it's recommended to create the assistant once and
    # reuse the ID.
    logger.info("Creating OpenAI Assistant...")
    assistant = client.beta.assistants.create(
        name="Portfolio Manager",
        instructions=SYSTEM_PROMPT,
        tools=OPENAI_TOOLS,
        model="gpt-4-turbo-preview",
    )
    logger.info(f"Assistant created with ID: {assistant.id}")

    logger.info("Creating a new conversation thread...")
    thread = client.beta.threads.create()
    logger.info(f"Thread created with ID: {thread.id}")

    print("\n--- Portfolio Manager Assistant ---")
    print("Ask me about your portfolio or market news. Type 'quit' to exit.")

    while True:
        try:
            user_input = input("\n> ")
            if user_input.lower() == "quit":
                break

            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=user_input,
            )

            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant.id,
            )
            logger.info(f"Run {run.id} created with status: {run.status}")

            while run.status not in ["completed", "failed"]:
                await asyncio.sleep(1)
                run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
                logger.info(f"Run {run.id} status: {run.status}")

                if run.status == "requires_action":
                    logger.info("Run requires tool actions.")
                    tool_outputs = []
                    if run.required_action:
                        for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                            logger.info(f"Dispatching tool call: {tool_call.function.name}")
                            output = await dispatch_tool_call(tool_call)
                            tool_outputs.append(
                                {
                                    "tool_call_id": tool_call.id,
                                    "output": json.dumps(output),
                                }
                            )

                        run = client.beta.threads.runs.submit_tool_outputs(
                            thread_id=thread.id,
                            run_id=run.id,
                            tool_outputs=tool_outputs,
                        )
                        logger.info("Tool outputs submitted.")

            if run.status == "completed":
                messages = client.beta.threads.messages.list(thread_id=thread.id)
                for message in messages.data:
                    if message.run_id == run.id and message.role == "assistant":
                        for content in message.content:
                            if content.type == "text":
                                print(f"\nAssistant: {content.text.value}")
                        break  # Only show the latest message for this run
            else:
                print(f"\nRun failed with status: {run.status}")
                if run.last_error:
                    print(f"Error: {run.last_error.message}")

        except Exception as e:
            logger.exception("An error occurred in the main loop.")
            print(f"An error occurred: {e}")
            break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
