# Portfolio Manager Agent

A demonstration of a portfolio management agent that combines MCP (Model Context Protocol) with the OpenAI Agent SDK. This example shows how to build an intelligent agent that can query and analyze portfolio holdings.

## Features

- **MCP Server**: Exposes portfolio data through standardized MCP tools
- **OpenAI Integration**: Uses GPT models to understand natural language queries
- **Portfolio Analytics**: View holdings, calculate profits/losses, track performance
- **Mock Data**: Includes sample portfolio data for demonstration
- **Market News Agent**: New MCP news server fetches headlines relevant to your portfolio and summarizes them

## Requirements

- Python 3.10+
- OpenAI API key
- uv (recommended) or pip

## Installation

1. **Install dependencies**:

   ```bash
   cd examples/portfoliomanager
   uv sync
   # or
   pip install -e ".[dev]"
   ```

2. **Set up OpenAI API key**:

   Create a `.env` file in the `examples/portfoliomanager` directory:

   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   ```

   You can obtain an API key from [OpenAI](https://platform.openai.com/api-keys).

## Usage

### Running the Portfolio Manager Agent

Run the interactive client:

```bash
uv run client.py
# or
python client.py
```

You can then interact with the agent using natural language:

```
You: Show me my portfolio

Agent: [Displays formatted portfolio with all holdings and metrics]

You: What is my total portfolio value?

Agent: [Shows total value calculation]

You: How is AAPL performing?

Agent: [Shows Apple's performance details]

You: What are my best performing stocks?

Agent: [Lists and analyzes top performers]
```

### Running the MCP Server Standalone

To run just the MCP server (useful for testing with MCP Inspector):

```bash
uv run portfolio-server
# or
python -m mcp_portfolio_server.server
```

To inspect with MCP CLI:

```bash
uv run mcp dev mcp_portfolio_server/server.py
```

### Quick Demo (No OpenAI Required)

Test the MCP server without OpenAI integration:

```bash
uv run demo.py
# or
python demo.py
```

This will connect to the MCP server and demonstrate all available tools with sample outputs.

### Market News Agent (Portfolio -> News -> Summary)

Run the chained agent that passes your portfolio to a news agent and summarizes market events:

```bash
uv run market_news_agent.py
# or
python market_news_agent.py
```

- If `OPENAI_API_KEY` is set, an LLM-generated summary is produced.
- Without a key, you still get a compact list of relevant headlines per holding.

To run each server standalone for inspection:

```bash
uv run portfolio-server     # portfolio MCP server
uv run news-server          # market news MCP server
```

## Portfolio Data

The portfolio data is stored in `portfolio_data.json` and includes:

- **Ticker**: Stock symbol (e.g., AAPL, MSFT)
- **Name**: Company name
- **Quantity**: Number of shares
- **Purchase Price**: Price per share when purchased
- **Current Price**: Current market price

Example holdings:
- Apple (AAPL): 50 shares
- Microsoft (MSFT): 30 shares
- Alphabet (GOOGL): 20 shares
- Amazon (AMZN): 15 shares
- Tesla (TSLA): 25 shares
- Meta (META): 40 shares
- NVIDIA (NVDA): 35 shares
- Netflix (NFLX): 18 shares

## Available Tools

The MCP server exposes five tools:

### 1. `get_all_holdings`

Returns all portfolio holdings with calculated values:
- Current total value
- Original purchase cost
- Profit/loss amount and percentage

**Returns:**
```json
{
  "holdings": [...],
  "summary": {
    "total_holdings": 8,
    "total_portfolio_value": 125430.50,
    "total_portfolio_cost": 105230.25,
    "overall_profit_loss": 20200.25
  }
}
```

### 2. `get_holding_by_ticker`

Get details for a specific stock by ticker symbol.

**Parameters:**
- `ticker` (string): Stock ticker symbol

**Example:**
```python
await session.call_tool("get_holding_by_ticker", {"ticker": "AAPL"})
```

### 3. `get_portfolio_summary`

Get overall portfolio statistics without individual holdings.

**Returns:**
```json
{
  "total_holdings": 8,
  "total_portfolio_value": 125430.50,
  "total_portfolio_cost": 105230.25,
  "overall_profit_loss": 20200.25,
  "overall_profit_loss_pct": 19.2
}
```

### 4. `assess_diversification`

Analyze diversification using sector and position concentration metrics.

Returns:

```json
{
  "sector_weights": {"Technology": 45.2, "Communication Services": 30.1, "Consumer Discretionary": 24.7},
  "position_weights": [
    {"ticker": "AAPL", "name": "Apple Inc.", "weight_pct": 18.5},
    {"ticker": "NVDA", "name": "NVIDIA Corporation", "weight_pct": 17.2}
  ],
  "hhi": 0.1625,
  "top_position_weight": 18.5,
  "num_holdings": 8,
  "notes": "Elevated overall concentration by HHI."
}
```

### 5. `assess_risk`

Provide a simple heuristic risk assessment (score 1–10 and factors):

```json
{
  "risk_score": 6.0,
  "risk_level": "Moderate",
  "factors": [
    "Elevated concentration by HHI (>=0.15).",
    "Includes higher-volatility names (e.g., TSLA/NVDA)."
  ],
  "inputs": {
    "top_position_weight_pct": 18.5,
    "hhi": 0.1625,
    "num_holdings": 8,
    "num_sectors": 3
  }
}
```

## Architecture

### MCP Server (`mcp_portfolio_server/server.py`)

- Built with FastMCP for easy tool definition
- Reads portfolio data from JSON file
- Exposes tools for querying portfolio information
- Calculates real-time profit/loss and percentages

### Client (`client.py`)

- Uses OpenAI API for natural language understanding
- Integrates MCP tools with OpenAI function calling
- Provides formatted, human-friendly output
- Supports interactive chat interface

## Customization

### Modify Portfolio Data

Edit `portfolio_data.json` to add, remove, or modify holdings:

```json
{
  "holdings": [
    {
      "ticker": "YOUR_TICKER",
      "name": "Company Name",
      "quantity": 100,
      "purchase_price": 150.00,
      "current_price": 175.00
    }
  ]
}
```

### Change OpenAI Model

Edit `client.py` to use a different model:

```python
agent = PortfolioAgent(api_key=api_key, model="gpt-4")
```

### Add New Tools

Add new tools to the MCP server in `mcp_portfolio_server/server.py`:

```python
@mcp.tool()
def my_new_tool(param: str) -> str:
    """Description of what the tool does."""
    # Your logic here
    return result
```

## Future Enhancements

Potential improvements:
- Add real-time price fetching from finance APIs
- Historical performance tracking
- Watch lists and alerts
- Transaction management
- Portfolio rebalancing suggestions
- Integration with real brokerage accounts (via APIs)

## License

MIT License - see LICENSE file in root directory

