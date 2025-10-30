"""Market News Agent: chains portfolio -> news -> summary.

Flow:
 1) Calls the portfolio MCP server to get current holdings.
 2) Passes holdings to the news MCP server to fetch headlines per ticker.
 3) If OPENAI_API_KEY is set, uses OpenAI to summarize relevant market events.
    Otherwise, prints a compact, non-LLM summary.
"""

import asyncio
import json
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

try:
    from openai import OpenAI
except Exception:  # noqa: BLE001 - optional
    OpenAI = None  # type: ignore


load_dotenv()


async def get_portfolio_snapshot(session: ClientSession) -> dict[str, Any]:
    result = await session.call_tool("get_all_holdings", {})
    return getattr(result, "structuredContent", {}) or {}


async def get_news_for_portfolio(news_session: ClientSession, portfolio: dict[str, Any]) -> dict[str, Any]:
    result = await news_session.call_tool("news_for_portfolio", {"portfolio_json": json.dumps(portfolio)})
    return getattr(result, "structuredContent", {}) or {}


def summarize_with_openai(portfolio: dict[str, Any], news: dict[str, Any]) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return ""
    client = OpenAI(api_key=api_key)
    system = (
        "You are a market analyst. You will receive a portfolio snapshot and per-ticker headlines. "
        "Summarize the most relevant market events and their potential impact on these holdings. "
        "Be concise and actionable."
    )
    content = json.dumps({"portfolio": portfolio, "news": news}, ensure_ascii=False)
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Analyze and summarize:\n{content}"},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""


def fallback_compact_summary(portfolio: dict[str, Any], news: dict[str, Any]) -> str:
    tickers = news.get("tickers", [])
    lines = ["Relevant headlines by holding:"]
    for t in tickers:
        items = news.get("news", {}).get(t, [])[:3]
        if not items:
            continue
        lines.append(f"- {t}:")
        for it in items:
            title = it.get("title", "").strip()
            link = it.get("link", "")
            lines.append(f"  • {title} ({link})")
    return "\n".join(lines)


async def main():
    from sys import executable as PYTHON_EXE
    portfolio_server_path = Path(__file__).parent / "mcp_portfolio_server" / "server.py"
    news_server_path = Path(__file__).parent / "mcp_news_server" / "server.py"

    async with AsyncExitStack() as stack:
        # Start portfolio server session
        portfolio_transport = await stack.enter_async_context(
            stdio_client(
                StdioServerParameters(
                    command=PYTHON_EXE,
                    args=[str(portfolio_server_path)],
                    env=os.environ.copy(),
                )
            )
        )
        p_read, p_write = portfolio_transport
        portfolio_session = await stack.enter_async_context(ClientSession(p_read, p_write))
        await portfolio_session.initialize()

        # Start news server session
        news_transport = await stack.enter_async_context(
            stdio_client(
                StdioServerParameters(
                    command=PYTHON_EXE,
                    args=[str(news_server_path)],
                    env=os.environ.copy(),
                )
            )
        )
        n_read, n_write = news_transport
        news_session = await stack.enter_async_context(ClientSession(n_read, n_write))
        await news_session.initialize()

        # Chain calls
        portfolio = await get_portfolio_snapshot(portfolio_session)
        news = await get_news_for_portfolio(news_session, portfolio)

        report = summarize_with_openai(portfolio, news)
        if not report:
            report = fallback_compact_summary(portfolio, news)

        print("=" * 80)
        print("MARKET NEWS SUMMARY (Relevant to Portfolio)")
        print("=" * 80)
        print(report or "No relevant news found.")


if __name__ == "__main__":
    asyncio.run(main())


