"""MCP News server: fetch market news and summarize per portfolio/ticker.

Uses Google News RSS for simple, no-key fetching.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.parse
from typing import Any

import feedparser
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("Market News")


def _google_news_rss_query(query: str) -> str:
    # Example: https://news.google.com/rss/search?q=AAPL%20stock&hl=en-US&gl=US&ceid=US:en
    q = urllib.parse.quote_plus(query)
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def _parse_feed(url: str, max_items: int) -> list[dict[str, Any]]:
    parsed = feedparser.parse(url)
    items: list[dict[str, Any]] = []
    for entry in parsed.entries[:max_items]:
        published = None
        if getattr(entry, "published_parsed", None):
            published = dt.datetime(*entry.published_parsed[:6]).isoformat()
        items.append(
            {
                "title": getattr(entry, "title", ""),
                "link": getattr(entry, "link", ""),
                "published": published,
                "source": getattr(entry, "source", {}).get("title") if getattr(entry, "source", None) else None,
            }
        )
    return items


@mcp.tool()
def fetch_symbol_news(ticker: str, max_items: int = 5) -> dict[str, Any]:
    """Fetch latest news for a ticker via Google News RSS.

    Returns: { ticker, items: [{title,link,published,source}] }
    """
    url = _google_news_rss_query(f"{ticker} stock")
    items = _parse_feed(url, max_items)
    return {"ticker": ticker.upper(), "items": items}


@mcp.tool()
def news_for_portfolio(portfolio_json: str, max_per_symbol: int = 3) -> dict[str, Any]:
    """Fetch top headlines for each symbol in a portfolio snapshot.

    Args:
      portfolio_json: JSON string with { holdings: [{ticker, ...}, ...] }
      max_per_symbol: max items per ticker

    Returns: { tickers: [...], news: {TICKER: [items...]}}.
    """
    try:
        portfolio = json.loads(portfolio_json)
    except json.JSONDecodeError:
        return {"error": "Invalid portfolio_json; must be JSON string."}

    holdings = portfolio.get("holdings", [])
    tickers = sorted({h.get("ticker", "").upper() for h in holdings if h.get("ticker")})
    news: dict[str, list[dict[str, Any]]] = {}
    for t in tickers:
        url = _google_news_rss_query(f"{t} stock")
        news[t] = _parse_feed(url, max_per_symbol)

    return {"tickers": tickers, "news": news}


def main() -> int:
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    from sys import exit

    exit(main())


