"""Simple demo script to test the portfolio MCP server without OpenAI."""

import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def demo_portfolio():
    """Demonstrate portfolio MCP server functionality."""
    server_path = Path(__file__).parent / "mcp_portfolio_server" / "server.py"
    
    from sys import executable as PYTHON_EXE
    server_params = StdioServerParameters(command=PYTHON_EXE, args=[str(server_path)])
    
    print("=" * 80)
    print("PORTFOLIO MCP SERVER DEMO")
    print("=" * 80)
    print()
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List available tools
            print("Available Tools:")
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")
            print()
            
            # Get portfolio summary
            print("1. Getting Portfolio Summary:")
            print("-" * 80)
            result = await session.call_tool("get_portfolio_summary", {})
            if hasattr(result, 'structuredContent') and result.structuredContent:
                summary = result.structuredContent
                print(f"Total Holdings: {summary['total_holdings']}")
                print(f"Total Portfolio Value: ${summary['total_portfolio_value']:,.2f}")
                print(f"Total Portfolio Cost: ${summary['total_portfolio_cost']:,.2f}")
                print(f"Overall Profit/Loss: ${summary['overall_profit_loss']:,.2f}")
                print(f"Overall P/L Percentage: {summary['overall_profit_loss_pct']:.2f}%")
            print()
            
            # Get all holdings
            print("2. Getting All Holdings:")
            print("-" * 80)
            result = await session.call_tool("get_all_holdings", {})
            if hasattr(result, 'structuredContent') and result.structuredContent:
                data = result.structuredContent
                holdings = data.get('holdings', [])
                
                # Display as table
                print(f"{'Ticker':<8} {'Name':<25} {'Qty':>6} {'Cur Price':>12} "
                      f"{'Value':>12} {'P/L':>12} {'P/L %':>8}")
                print("-" * 100)
                
                for h in holdings:
                    pl_sign = "+" if h['profit_loss'] >= 0 else ""
                    pct_sign = "+" if h['profit_loss_pct'] >= 0 else ""
                    print(f"{h['ticker']:<8} {h['name'][:24]:<25} {h['quantity']:>6} "
                          f"${h['current_price']:>11.2f} ${h['total_value']:>11.2f} "
                          f"{pl_sign}${abs(h['profit_loss']):>11.2f} "
                          f"{pct_sign}{abs(h['profit_loss_pct']):>7.2f}%")
                print()
                
                # Display summary
                summary = data.get('summary', {})
                print(f"Summary: {summary['total_holdings']} holdings | "
                      f"Total Value: ${summary['total_portfolio_value']:,.2f} | "
                      f"Overall P/L: ${summary['overall_profit_loss']:,.2f}")
                print()
            
            # Get specific holding
            print("3. Getting Specific Holding (AAPL):")
            print("-" * 80)
            result = await session.call_tool("get_holding_by_ticker", {"ticker": "AAPL"})
            if hasattr(result, 'structuredContent') and result.structuredContent:
                holding = result.structuredContent
                if 'error' not in holding:
                    print(f"Ticker: {holding['ticker']}")
                    print(f"Name: {holding['name']}")
                    print(f"Quantity: {holding['quantity']}")
                    print(f"Purchase Price: ${holding['purchase_price']:.2f}")
                    print(f"Current Price: ${holding['current_price']:.2f}")
                    print(f"Total Value: ${holding['total_value']:.2f}")
                    print(f"Total Cost: ${holding['total_cost']:.2f}")
                    print(f"Profit/Loss: ${holding['profit_loss']:.2f}")
                    print(f"P/L Percentage: {holding['profit_loss_pct']:.2f}%")
                else:
                    print(f"Error: {holding['error']}")
            print()
            
            print("=" * 80)
            print("Demo completed successfully!")
            print("=" * 80)


if __name__ == "__main__":
    asyncio.run(demo_portfolio())

