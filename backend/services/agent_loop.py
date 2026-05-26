"""Multi-turn agent loop with tool calling support."""

import json
import asyncio
from typing import AsyncGenerator
from services.tools import TOOL_MAP, get_tool_definitions
from llm.base import LLMProvider
from logger import get_logger

logger = get_logger("agent_loop")

MAX_TURNS = 10
TOOL_TURN_WARN = 5
TOOL_TURN_FORCE = 7


async def _execute_tool(tool_name: str, args: dict) -> tuple:
    """Execute a single tool and return (result, summary_str)."""
    tool_fn = TOOL_MAP.get(tool_name)
    if not tool_fn:
        return f"Tool '{tool_name}' not found", "Tool not found"

    try:
        if asyncio.iscoroutinefunction(tool_fn):
            result = await tool_fn(**args)
        else:
            result = tool_fn(**args)
    except Exception:
        logger.exception("Tool %s execution failed", tool_name)
        return "Tool execution failed", "Error during execution"

    if isinstance(result, list):
        summary = f"{len(result)} results"
    elif isinstance(result, str):
        summary = f"{len(result)} chars"
    else:
        summary = str(result)

    return result, summary


async def _process_tool_calls(
    messages: list[dict],
    tool_calls: list[dict],
    content: str | None,
    reasoning_content: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Execute each tool call and yield tool_call/tool_result events."""
    msg: dict = {"role": "assistant", "content": content, "tool_calls": tool_calls}
    if reasoning_content:
        msg["reasoning_content"] = reasoning_content
    messages.append(msg)

    for tc in tool_calls:
        fn = tc["function"]
        tool_name = fn["name"]
        try:
            args = json.loads(fn["arguments"])
        except json.JSONDecodeError:
            logger.warning("Failed to parse tool arguments for %s: %s", tool_name, fn.get("arguments", ""))
            args = {}

        yield {"type": "tool_call", "tool": tool_name, "args": args}

        result, summary = await _execute_tool(tool_name, args)

        yield {"type": "tool_result", "tool": tool_name, "result": summary}

        messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": json.dumps(result, ensure_ascii=False) if isinstance(result, (list, dict)) else str(result),
        })


async def agent_loop(
    messages: list[dict],
    model: str,
    provider: LLMProvider,
    tools: list[dict] | None = None,
    max_turns: int = MAX_TURNS,
    enable_tools: bool = True,
) -> AsyncGenerator[dict, None]:
    """Multi-turn agent loop. Set enable_tools=False to run without tool calling."""
    effective_tools = None
    if enable_tools:
        effective_tools = tools if tools is not None else get_tool_definitions()
    turn = 0
    tool_turns = 0

    while turn < max_turns:
        turn += 1

        try:
            response = await provider.chat_completion_with_tools_async(
                model=model,
                messages=messages,
                tools=effective_tools if effective_tools else None,
            )
        except Exception as e:
            logger.exception("LLM call failed at turn %d", turn)
            yield {"type": "agent_error", "error": "AI request failed, please try again"}
            return

        tool_calls = response.get("tool_calls")
        content = response.get("content")
        reasoning = response.get("reasoning_content")

        if content and not tool_calls:
            yield {"type": "agent_done", "text": content}
            return

        if not tool_calls:
            if reasoning:
                messages.append({"role": "assistant", "content": None, "reasoning_content": reasoning})
            if effective_tools:
                yield {"type": "agent_thinking", "content": "Thinking..."}
            continue

        if content and effective_tools:
            yield {"type": "agent_thinking", "content": content}

        tool_turns += 1
        if tool_turns >= TOOL_TURN_FORCE:
            effective_tools = None
            messages.append({
                "role": "system",
                "content": "You have done enough research. Stop using tools and generate the final content NOW based on what you have gathered. Do NOT search anymore — write the complete output immediately.",
            })
        elif tool_turns >= TOOL_TURN_WARN:
            messages.append({
                "role": "system",
                "content": "You should have enough information by now. Try to generate the content with what you have. Only search if absolutely essential for a missing piece.",
            })

        async for event in _process_tool_calls(messages, tool_calls, content, reasoning):
            yield event

    yield {
        "type": "agent_error",
        "error": f"Agent did not complete within {max_turns} turns.",
    }
