"""Interactive OpenAI Agent runner wired to local MCP servers via stdio.

Usage:
  uv run examples/portfoliomanager/agents/run_agent.py

Requires OPENAI_API_KEY in environment or .env.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

try:
    # When executed as a module (python -m ...)
    from .integration import OPENAI_TOOLS, dispatch_tool_call
except Exception:
    # When executed as a script (uv run agents/run_agent.py)
    from agents.integration import OPENAI_TOOLS, dispatch_tool_call  # type: ignore


SYSTEM_PROMPT = (
    "You are a portfolio assistant. You have tools to read a local MCP portfolio server "
    "and a news server. Use tools when asked about current portfolio data or headlines."
)


async def main() -> None:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Missing OPENAI_API_KEY. Set it in your environment or .env.")
        return

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    print("\n=== Portfolio Assistant (OpenAI Agents SDK + MCP stdio) ===\n")
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    while True:
        user = input("You: ").strip()
        if user.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break
        if not user:
            continue

        messages.append({"role": "user", "content": user})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=OPENAI_TOOLS,
            tool_choice="auto",
            temperature=0.2,
        )

        msg = response.choices[0].message
        tool_calls = msg.tool_calls or []

        if tool_calls:
            # Record assistant stub with tool calls
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in tool_calls
                    ],
                }
            )

            # Execute tools and append results
            for tc in tool_calls:
                tool_name = tc.function.name
                tool_args = tc.function.arguments
                result = await dispatch_tool_call(tool_name, tool_args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

            # Get final answer
            response = client.chat.completions.create(model=model, messages=messages, temperature=0.2)
            print(f"Agent: {response.choices[0].message.content}\n")
            continue

        print(f"Agent: {msg.content}\n")


if __name__ == "__main__":
    asyncio.run(main())


