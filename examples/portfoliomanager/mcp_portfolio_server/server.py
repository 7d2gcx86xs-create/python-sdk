"""MCP server for portfolio management."""

import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("Portfolio Manager")

# Load portfolio data on startup
PORTFOLIO_FILE = Path(__file__).parent.parent / "portfolio_data.json"


def load_portfolio() -> dict[str, Any]:
    """Load portfolio data from JSON file."""
    if not PORTFOLIO_FILE.exists():
        return {"holdings": []}
    
    with open(PORTFOLIO_FILE, "r") as f:
        return json.load(f)


@mcp.tool()
def get_all_holdings() -> dict[str, Any]:
    """Get all portfolio holdings with current values and profit/loss.
    
    Returns:
        Dictionary containing list of holdings with:
        - ticker: Stock ticker symbol
        - name: Company name
        - quantity: Number of shares owned
        - purchase_price: Price per share when purchased
        - current_price: Current market price per share
        - total_value: Current total value (quantity * current_price)
        - total_cost: Original purchase cost (quantity * purchase_price)
        - profit_loss: Current profit/loss amount
        - profit_loss_pct: Profit/loss percentage
    """
    portfolio = load_portfolio()
    holdings = portfolio.get("holdings", [])
    
    # Enrich holdings with calculated values
    enriched_holdings = []
    for holding in holdings:
        total_cost = holding["quantity"] * holding["purchase_price"]
        total_value = holding["quantity"] * holding["current_price"]
        profit_loss = total_value - total_cost
        profit_loss_pct = (profit_loss / total_cost) * 100 if total_cost > 0 else 0
        
        enriched_holding = {
            "ticker": holding["ticker"],
            "name": holding["name"],
            "quantity": holding["quantity"],
            "purchase_price": holding["purchase_price"],
            "current_price": holding["current_price"],
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "profit_loss": round(profit_loss, 2),
            "profit_loss_pct": round(profit_loss_pct, 2),
        }
        enriched_holdings.append(enriched_holding)
    
    return {
        "holdings": enriched_holdings,
        "summary": {
            "total_holdings": len(enriched_holdings),
            "total_portfolio_value": round(sum(h["total_value"] for h in enriched_holdings), 2),
            "total_portfolio_cost": round(sum(h["total_cost"] for h in enriched_holdings), 2),
            "overall_profit_loss": round(
                sum(h["profit_loss"] for h in enriched_holdings), 2
            ),
        },
    }


@mcp.tool()
def get_holding_by_ticker(ticker: str) -> dict[str, Any]:
    """Get details for a specific holding by ticker symbol.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT')
    
    Returns:
        Dictionary with holding details, or error message if not found
    """
    portfolio = load_portfolio()
    holdings = portfolio.get("holdings", [])
    
    for holding in holdings:
        if holding["ticker"].upper() == ticker.upper():
            total_cost = holding["quantity"] * holding["purchase_price"]
            total_value = holding["quantity"] * holding["current_price"]
            profit_loss = total_value - total_cost
            profit_loss_pct = (profit_loss / total_cost) * 100 if total_cost > 0 else 0
            
            return {
                "ticker": holding["ticker"],
                "name": holding["name"],
                "quantity": holding["quantity"],
                "purchase_price": holding["purchase_price"],
                "current_price": holding["current_price"],
                "total_value": round(total_value, 2),
                "total_cost": round(total_cost, 2),
                "profit_loss": round(profit_loss, 2),
                "profit_loss_pct": round(profit_loss_pct, 2),
            }
    
    return {"error": f"Holding with ticker '{ticker}' not found"}


@mcp.tool()
def get_portfolio_summary() -> dict[str, Any]:
    """Get a summary of the entire portfolio.
    
    Returns:
        Dictionary with overall portfolio statistics including:
        - Total number of holdings
        - Total current value
        - Total original cost
        - Overall profit/loss amount and percentage
    """
    portfolio = load_portfolio()
    holdings = portfolio.get("holdings", [])
    
    total_holdings = len(holdings)
    total_value = sum(holding["quantity"] * holding["current_price"] for holding in holdings)
    total_cost = sum(holding["quantity"] * holding["purchase_price"] for holding in holdings)
    overall_profit_loss = total_value - total_cost
    overall_profit_loss_pct = (overall_profit_loss / total_cost) * 100 if total_cost > 0 else 0
    
    return {
        "total_holdings": total_holdings,
        "total_portfolio_value": round(total_value, 2),
        "total_portfolio_cost": round(total_cost, 2),
        "overall_profit_loss": round(overall_profit_loss, 2),
        "overall_profit_loss_pct": round(overall_profit_loss_pct, 2),
    }


# Minimal sector mapping for common demo tickers
_SECTOR_BY_TICKER: dict[str, str] = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "GOOGL": "Communication Services",
    "AMZN": "Consumer Discretionary",
    "TSLA": "Consumer Discretionary",
    "META": "Communication Services",
    "NVDA": "Technology",
    "NFLX": "Communication Services",
}


def _current_value(holding: dict[str, Any]) -> float:
    return float(holding["quantity"]) * float(holding["current_price"])


@mcp.tool()
def assess_diversification() -> dict[str, Any]:
    """Assess portfolio diversification using sector weights and concentration metrics.

    Returns a dictionary with:
    - sector_weights: mapping of sector -> percent of portfolio value
    - position_weights: top positions by weight
    - hhi: Herfindahl-Hirschman Index (0-1), lower is more diversified
    - top_position_weight: weight of largest single position
    - num_holdings: number of holdings
    - notes: brief interpretation
    """
    portfolio = load_portfolio()
    holdings = portfolio.get("holdings", [])
    if not holdings:
        return {
            "sector_weights": {},
            "position_weights": [],
            "hhi": 0.0,
            "top_position_weight": 0.0,
            "num_holdings": 0,
            "notes": "No holdings found.",
        }

    # Compute weights by current value
    values = [(_current_value(h), h) for h in holdings]
    total = sum(v for v, _ in values) or 1.0
    position_weights = sorted(
        [
            {
                "ticker": h["ticker"],
                "name": h["name"],
                "weight_pct": round((v / total) * 100.0, 2),
            }
            for v, h in values
        ],
        key=lambda x: x["weight_pct"],
        reverse=True,
    )

    # Sector weights
    sector_totals: dict[str, float] = {}
    for v, h in values:
        sector = _SECTOR_BY_TICKER.get(h["ticker"].upper(), "Unknown")
        sector_totals[sector] = sector_totals.get(sector, 0.0) + v
    sector_weights = {k: round((v / total) * 100.0, 2) for k, v in sector_totals.items()}

    # Concentration metrics
    weights = [v / total for v, _ in values]
    hhi = round(sum(w * w for w in weights), 4)  # 0..1
    top_w = round(max(weights) * 100.0, 2)

    # Notes
    notes: list[str] = []
    if top_w >= 25.0:
        notes.append("High single-position concentration (top holding >= 25%).")
    if hhi >= 0.15:  # heuristic threshold
        notes.append("Elevated overall concentration by HHI.")
    if len(sector_weights) <= 2:
        notes.append("Limited sector diversification.")
    if not notes:
        notes.append("Diversification appears reasonable for a simple demo portfolio.")

    return {
        "sector_weights": sector_weights,
        "position_weights": position_weights[:10],
        "hhi": hhi,
        "top_position_weight": top_w,
        "num_holdings": len(holdings),
        "notes": " ".join(notes),
    }


@mcp.tool()
def assess_risk() -> dict[str, Any]:
    """Provide a simple heuristic risk assessment (score 1-10) with factors.

    The assessment considers:
      - Position concentration (top position weight)
      - Overall concentration (HHI)
      - Sector concentration (few sectors, heavy tech/consumer discretionary)
      - Presence of historically higher-volatility tickers (e.g., TSLA, NVDA)
      - Number of holdings
    """
    # Use diversification as inputs
    div = assess_diversification()
    sector_weights = div.get("sector_weights", {})
    top_w = float(div.get("top_position_weight", 0.0))
    hhi = float(div.get("hhi", 0.0))
    num_holdings = int(div.get("num_holdings", 0))

    # Heuristic scoring 1..10 (higher = riskier)
    score = 1.0
    factors: list[str] = []

    # Top position concentration
    if top_w >= 40:
        score += 4
        factors.append("Very high single-position concentration (>=40%).")
    elif top_w >= 25:
        score += 2
        factors.append("High single-position concentration (>=25%).")
    elif top_w >= 15:
        score += 1
        factors.append("Moderate single-position concentration (>=15%).")

    # HHI concentration
    if hhi >= 0.25:
        score += 3
        factors.append("High overall concentration by HHI (>=0.25).")
    elif hhi >= 0.15:
        score += 2
        factors.append("Elevated concentration by HHI (>=0.15).")
    elif hhi >= 0.10:
        score += 1
        factors.append("Some concentration by HHI (>=0.10).")

    # Sector concentration
    if len(sector_weights) <= 2:
        score += 2
        factors.append("Limited sector diversification (<=2 sectors).")
    elif len(sector_weights) <= 3:
        score += 1
        factors.append("Concentrated across few sectors (<=3 sectors).")

    # Heuristic for volatile names
    volatile_names = {"TSLA", "NVDA"}
    portfolio = load_portfolio()
    holdings = portfolio.get("holdings", [])
    tickers = {h["ticker"].upper() for h in holdings}
    if tickers & volatile_names:
        score += 1
        factors.append("Includes higher-volatility names (e.g., TSLA/NVDA).")

    # Number of holdings
    if num_holdings <= 4 and num_holdings > 0:
        score += 1
        factors.append("Few holdings (<=4) increases idiosyncratic risk.")

    # Clamp and label
    score = max(1.0, min(10.0, score))
    if score >= 8:
        label = "High"
    elif score >= 5:
        label = "Moderate"
    else:
        label = "Low"

    return {
        "risk_score": round(score, 1),
        "risk_level": label,
        "factors": factors,
        "inputs": {
            "top_position_weight_pct": top_w,
            "hhi": hhi,
            "num_holdings": num_holdings,
            "num_sectors": len(sector_weights),
        },
    }


def main() -> int:
    """Run the MCP server."""
    # FastMCP provides a synchronous runner for stdio by default
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    from sys import exit
    
    exit(main())

