"""Portfolio Manager Agent Client using OpenAI Agent SDK with MCP.

This script provides an interactive command-line interface to chat with
a portfolio manager assistant. It uses the OpenAI Assistants API to create
and manage the assistant, conversation threads, and runs.

This client follows the "Custom UX" guide from the OpenAI documentation:
https://developers.openai.com/apps-sdk/build/custom-ux

Usage:
  uv run examples/portfoliomanager/client.py

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

try:
    # When executed as a script from the project root
    from agents.integration import OPENAI_TOOLS, dispatch_tool_call
except (ImportError, ModuleNotFoundError):
    # Support for different execution contexts
    from examples.portfoliomanager.agents.integration import (  # type: ignore
        OPENAI_TOOLS,
        dispatch_tool_call,
    )


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# System prompt for the assistant
SYSTEM_PROMPT = (
    "You are a portfolio assistant. You have tools to read a local MCP portfolio server "
    "and a news server. Use tools when asked about current portfolio data or headlines."
)


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
