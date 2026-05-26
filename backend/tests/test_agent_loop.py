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
