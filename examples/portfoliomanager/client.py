"""Portfolio Manager Agent Client using OpenAI Agent SDK with MCP."""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class PortfolioAgent:
    """Portfolio management agent that uses MCP server and OpenAI."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """Initialize the portfolio agent.
        
        Args:
            api_key: OpenAI API key
            model: OpenAI model to use (default: gpt-4o-mini)
        """
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(api_key=api_key)
        
        # Get path to server.py relative to this file
        server_path = Path(__file__).parent / "mcp_portfolio_server" / "server.py"
        self.server_params = StdioServerParameters(
            command="python",
            args=[str(server_path)],
            env=os.environ.copy()
        )
    
    async def get_tools(self, session: ClientSession) -> list[dict[str, Any]]:
        """Get available tools from MCP server formatted for OpenAI.
        
        Args:
            session: MCP client session
            
        Returns:
            List of tools in OpenAI format
        """
        tools_response = await session.list_tools()
        tools = []
        
        for tool in tools_response.tools:
            tool_def = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema
                }
            }
            tools.append(tool_def)
        
        return tools
    
    async def format_holdings_for_display(self, holdings_data: dict[str, Any]) -> str:
        """Format holdings data for display.
        
        Args:
            holdings_data: Dictionary containing portfolio data from MCP server
            
        Returns:
            Formatted string for display
        """
        holdings = holdings_data.get("holdings", [])
        summary = holdings_data.get("summary", {})
        
        output = "\n" + "=" * 80 + "\n"
        output += "PORTFOLIO HOLDINGS\n"
        output += "=" * 80 + "\n\n"
        
        if not holdings:
            output += "No holdings found in portfolio.\n"
            return output
        
        # Header
        output += f"{'Ticker':<8} {'Name':<25} {'Qty':>6} {'Cur Price':>12} "
        output += f"{'Value':>12} {'P/L':>12} {'P/L %':>8}\n"
        output += "-" * 100 + "\n"
        
        # Holdings
        for holding in holdings:
            ticker = holding["ticker"]
            name = holding["name"][:24]  # Truncate long names
            qty = holding["quantity"]
            curr_price = f"${holding['current_price']:.2f}"
            value = f"${holding['total_value']:.2f}"
            
            # Color code profit/loss
            pl = holding["profit_loss"]
            pl_pct = holding["profit_loss_pct"]
            if pl >= 0:
                pl_str = f"+${abs(pl):.2f}"
                pl_pct_str = f"+{abs(pl_pct):.2f}%"
            else:
                pl_str = f"-${abs(pl):.2f}"
                pl_pct_str = f"-{abs(pl_pct):.2f}%"
            
            output += f"{ticker:<8} {name:<25} {qty:>6} {curr_price:>12} "
            output += f"{value:>12} {pl_str:>12} {pl_pct_str:>8}\n"
        
        output += "\n" + "-" * 100 + "\n"
        
        # Summary
        total_value = summary.get("total_portfolio_value", 0)
        total_profit_loss = summary.get("overall_profit_loss", 0)
        total_holdings = summary.get("total_holdings", 0)
        
        if total_profit_loss >= 0:
            pl_summary = f"+${abs(total_profit_loss):.2f}"
        else:
            pl_summary = f"-${abs(total_profit_loss):.2f}"
        
        output += f"Summary: {total_holdings} holdings | "
        output += f"Total Value: ${total_value:.2f} | "
        output += f"Overall P/L: {pl_summary}\n"
        output += "=" * 80 + "\n"
        
        return output
    
    async def chat_with_agent(self, user_query: str) -> str:
        """Chat with the portfolio agent.
        
        Args:
            user_query: User's question about the portfolio
            
        Returns:
            Agent's response
        """
        messages = [
            {
                "role": "system",
                "content": """You are a helpful portfolio management assistant. 
You have access to tools that can query portfolio holdings. 
When asked about the portfolio, use the available tools to get current information.
Always be helpful, professional, and accurate in your responses.
When displaying portfolio data, be sure to include key metrics like current value, profit/loss, etc."""
            },
            {
                "role": "user",
                "content": user_query
            }
        ]
        
        try:
            async with stdio_client(self.server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Get available tools
                    tools = await self.get_tools(session)
                    
                    # First call to OpenAI to determine if tools are needed
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        tools=tools,
                        tool_choice="auto"
                    )
                    
                    message = response.choices[0].message
                    
                    # Handle tool calls
                    if message.tool_calls:
                        messages.append({
                            "role": "assistant",
                            "content": message.content or "",
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                                }
                                for tc in message.tool_calls
                            ]
                        })
                        
                        for tool_call in message.tool_calls:
                            func_name = tool_call.function.name
                            func_args = json.loads(tool_call.function.arguments)
                            
                            logger.info(f"Calling tool: {func_name} with args: {func_args}")
                            
                            # Call MCP tool
                            result = await session.call_tool(func_name, func_args)
                            
                            # Extract structured content
                            tool_result_data = None
                            if hasattr(result, 'structuredContent') and result.structuredContent:
                                tool_result_data = result.structuredContent
                            
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": json.dumps(tool_result_data) if tool_result_data else "Tool executed successfully"
                            })
                        
                        # Get final response from OpenAI with tool results
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=messages
                        )
                    
                    return response.choices[0].message.content or "No response generated"
        
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return f"I encountered an error: {str(e)}. Please try again."
    
    async def display_portfolio(self) -> None:
        """Display the current portfolio holdings."""
        try:
            async with stdio_client(self.server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Get all holdings
                    result = await session.call_tool("get_all_holdings", {})
                    
                    # Extract structured content
                    holdings_data = None
                    if hasattr(result, 'structuredContent') and result.structuredContent:
                        holdings_data = result.structuredContent
                    
                    if holdings_data:
                        formatted = await self.format_holdings_for_display(holdings_data)
                        print(formatted)
                    else:
                        print("Unable to retrieve portfolio data.")
        
        except Exception as e:
            logger.error(f"Error displaying portfolio: {e}")
            print(f"Error: {str(e)}")


async def main():
    """Main entry point for the portfolio manager agent."""
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment variables.")
        print("Please set OPENAI_API_KEY in your .env file or environment.")
        return
    
    agent = PortfolioAgent(api_key=api_key)
    
    print("\n" + "=" * 80)
    print("PORTFOLIO MANAGER AGENT")
    print("=" * 80)
    print("\nThis agent can answer questions about your portfolio holdings.")
    print("You can ask questions like:")
    print("  - 'Show me my portfolio'")
    print("  - 'What is my total portfolio value?'")
    print("  - 'How is AAPL performing?'")
    print("  - 'What are my best performing stocks?'")
    print("  - 'Show me my biggest losses'")
    print("\nType 'quit' or 'exit' to stop.")
    print("=" * 80 + "\n")
    
    while True:
        try:
            query = input("You: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye!")
                break
            
            if not query:
                continue
            
            print("\nAgent: ", end='', flush=True)
            response = await agent.chat_with_agent(query)
            print(response)
            print()
        
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            print(f"Error: {str(e)}\n")


if __name__ == "__main__":
    asyncio.run(main())

