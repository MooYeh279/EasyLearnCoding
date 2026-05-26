import pytest


class FakeProvider:
    """Mock LLM provider for testing agent loop."""

    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.call_count = 0

    async def chat_completion_with_tools_async(
        self, model: str, messages: list[dict], tools: list[dict] | None = None, **kwargs
    ) -> dict:
        if self.call_count >= len(self.responses):
            return {"content": "fallback", "tool_calls": None}
        resp = self.responses[self.call_count]
        self.call_count += 1
        return resp


class FailingProvider:
    """Mock LLM provider that raises on every call."""

    async def chat_completion_with_tools_async(
        self, model: str, messages: list[dict], tools: list[dict] | None = None, **kwargs
    ) -> dict:
        raise RuntimeError("API unavailable")


@pytest.mark.asyncio
async def test_agent_loop_direct_answer() -> None:
    """Agent loop should yield agent_done when LLM returns content without tool calls."""
    from services.agent_loop import agent_loop

    provider = FakeProvider([
        {"content": "Hello! How can I help?", "tool_calls": None},
    ])

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Hi"}],
        model="test-model",
        provider=provider,
        tools=[],
    ):
        events.append(event)

    assert len(events) == 1
    assert events[0]["type"] == "agent_done"
    assert events[0]["text"] == "Hello! How can I help?"


@pytest.mark.asyncio
async def test_agent_loop_with_tool_calls() -> None:
    """Agent loop should execute tool calls, yield result summaries as strings."""
    from services.agent_loop import agent_loop

    provider = FakeProvider([
        {
            "content": None,
            "tool_calls": [{"id": "1", "type": "function", "function": {"name": "web_search", "arguments": '{"query": "test"}'}}],
        },
        {"content": "Based on search results, the answer is 42.", "tool_calls": None},
    ])

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "What is the answer?"}],
        model="test-model",
        provider=provider,
        tools=[{"type": "function", "function": {"name": "web_search", "parameters": {}}}],
    ):
        events.append(event)

    types = [e["type"] for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "agent_done" in types

    tool_result = next(e for e in events if e["type"] == "tool_result")
    assert isinstance(tool_result["result"], str)

    done_event = events[-1]
    assert done_event["text"] == "Based on search results, the answer is 42."


@pytest.mark.asyncio
async def test_agent_loop_max_turns() -> None:
    """Agent loop should terminate after max_turns even if LLM keeps requesting tools."""
    from services.agent_loop import agent_loop

    provider = FakeProvider([
        {"content": None, "tool_calls": [{"id": str(i), "type": "function", "function": {"name": "web_search", "arguments": '{"query": "x"}'}}]}
        for i in range(20)
    ])

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Search"}],
        model="test-model",
        provider=provider,
        tools=[{"type": "function", "function": {"name": "web_search", "parameters": {}}}],
        max_turns=3,
    ):
        events.append(event)

    error_types = [e for e in events if e["type"] == "agent_error"]
    assert len(error_types) > 0


@pytest.mark.asyncio
async def test_agent_loop_llm_error() -> None:
    """Agent loop should yield agent_error when LLM call fails."""
    from services.agent_loop import agent_loop

    provider = FailingProvider()

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Hi"}],
        model="test-model",
        provider=provider,
        tools=[],
    ):
        events.append(event)

    assert len(events) == 1
    assert events[0]["type"] == "agent_error"
    assert "AI request failed" in events[0]["error"]


@pytest.mark.asyncio
async def test_agent_loop_unknown_tool() -> None:
    """Unknown tool should produce error result but not crash loop."""
    from services.agent_loop import agent_loop

    provider = FakeProvider([
        {
            "content": None,
            "tool_calls": [{"id": "1", "type": "function", "function": {"name": "unknown_tool", "arguments": '{}'}}],
        },
        {"content": "I tried but the tool wasn't available.", "tool_calls": None},
    ])

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Use an unknown tool"}],
        model="test-model",
        provider=provider,
        tools=[{"type": "function", "function": {"name": "unknown_tool", "parameters": {}}}],
    ):
        events.append(event)

    types = [e["type"] for e in events]
    assert "agent_done" in types


@pytest.mark.asyncio
async def test_agent_loop_thinking_with_tool_calls() -> None:
    """When LLM returns content alongside tool_calls, content is yielded as agent_thinking."""
    from services.agent_loop import agent_loop

    provider = FakeProvider([
        {
            "content": "Let me search for that information.",
            "tool_calls": [{"id": "1", "type": "function", "function": {"name": "web_search", "arguments": '{"query": "test"}'}}],
        },
        {"content": "Done.", "tool_calls": None},
    ])

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Search"}],
        model="test-model",
        provider=provider,
        tools=[{"type": "function", "function": {"name": "web_search", "parameters": {}}}],
    ):
        events.append(event)

    thinking_events = [e for e in events if e["type"] == "agent_thinking"]
    assert len(thinking_events) >= 1
    assert thinking_events[0]["content"] == "Let me search for that information."

    # Verify ordering: agent_thinking appears before tool_call
    thinking_idx = next(i for i, e in enumerate(events) if e["type"] == "agent_thinking")
    tool_call_idx = next(i for i, e in enumerate(events) if e["type"] == "tool_call")
    assert thinking_idx < tool_call_idx


@pytest.mark.asyncio
async def test_agent_loop_arguments_json_error() -> None:
    """Malformed tool arguments JSON should not crash the loop."""
    from services.agent_loop import agent_loop

    provider = FakeProvider([
        {
            "content": None,
            "tool_calls": [{"id": "1", "type": "function", "function": {"name": "web_search", "arguments": 'not valid json'}}],
        },
        {"content": "Retry completed.", "tool_calls": None},
    ])

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Search"}],
        model="test-model",
        provider=provider,
        tools=[{"type": "function", "function": {"name": "web_search", "parameters": {}}}],
    ):
        events.append(event)

    done = next(e for e in events if e["type"] == "agent_done")
    assert done["text"] == "Retry completed."


@pytest.mark.asyncio
async def test_agent_loop_force_stop_rejects_tool_calls() -> None:
    """After force_stop, if model still returns tool_calls via standard channel,
    agent_loop should reject them and eventually get a text response."""
    from services.agent_loop import agent_loop, TOOL_TURN_FORCE

    tool_call_resp = {
        "content": None,
        "tool_calls": [{"id": "1", "type": "function", "function": {"name": "web_search", "arguments": '{"query": "more"}'}}],
    }
    # First TOOL_TURN_FORCE calls execute tools, then model calls tools again
    # (force_stop triggers), then finally gives a text answer.
    responses = [tool_call_resp] * TOOL_TURN_FORCE
    # After force_stop, model tries one more tool call
    responses.append(tool_call_resp)
    # Then model finally outputs text
    responses.append({"content": "Final answer based on gathered info.", "tool_calls": None})

    provider = FakeProvider(responses)

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Search a lot"}],
        model="test-model",
        provider=provider,
        tools=[{"type": "function", "function": {"name": "web_search", "parameters": {}}}],
    ):
        events.append(event)

    done = next(e for e in events if e["type"] == "agent_done")
    assert done["text"] == "Final answer based on gathered info."

    # The last tool_call after force_stop should NOT produce a tool_result
    # (tools are rejected, not executed)
    tool_results = [e for e in events if e["type"] == "tool_result"]
    assert len(tool_results) == TOOL_TURN_FORCE


@pytest.mark.asyncio
async def test_agent_loop_tools_always_passed() -> None:
    """Tools should always be passed to the API even after force_stop,
    so the model uses standard tool_calls channel instead of proprietary tags."""
    from services.agent_loop import agent_loop

    captured_tools: list[list[dict] | None] = []

    class CapturingProvider:
        async def chat_completion_with_tools_async(
            self, model: str, messages: list[dict], tools: list[dict] | None = None, **kwargs
        ) -> dict:
            captured_tools.append(tools)
            if not captured_tools or len(captured_tools) <= 1:
                return {
                    "content": None,
                    "tool_calls": [{"id": "1", "type": "function", "function": {"name": "web_search", "arguments": '{"query": "x"}'}}],
                }
            return {"content": "Done.", "tool_calls": None}

    provider = CapturingProvider()
    tool_defs = [{"type": "function", "function": {"name": "web_search", "parameters": {}}}]

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Search"}],
        model="test-model",
        provider=provider,
        tools=tool_defs,
    ):
        events.append(event)

    # Every call should have received tools (never None)
    assert all(t is not None for t in captured_tools)
