import pytest
from unittest.mock import patch


class FakeProvider:
    """Mock LLM provider for testing."""

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


@pytest.mark.asyncio
async def test_generate_lesson_stream() -> None:
    """generate_lesson_stream_async should yield agent_done with generated content."""
    from services.ai_service import generate_lesson_stream_async

    provider = FakeProvider([
        {"content": "# Lesson Content", "tool_calls": None},
    ])
    with (
        patch("services.ai_service.get_provider", return_value=provider),
        patch("services.ai_service.get_model", return_value="test-model"),
    ):
        events = [e async for e in generate_lesson_stream_async("Topic", "Python", "Section", "Lesson")]

    assert events[0]["type"] == "agent_done"
    assert events[0]["text"] == "# Lesson Content"


@pytest.mark.asyncio
async def test_generate_lesson_stream_with_tools() -> None:
    """generate_lesson_stream_async should only yield agent_done/agent_error,
    not intermediate tool_call/tool_result events."""
    from services.ai_service import generate_lesson_stream_async

    provider = FakeProvider([
        {
            "content": "Let me search.",
            "tool_calls": [{"id": "1", "type": "function", "function": {"name": "web_search", "arguments": '{"query": "test"}'}}],
        },
        {"content": "Final answer.", "tool_calls": None},
    ])
    with (
        patch("services.ai_service.get_provider", return_value=provider),
        patch("services.ai_service.get_model", return_value="test-model"),
    ):
        events = [e async for e in generate_lesson_stream_async("Topic", "Python", "Section", "Lesson")]

    # Only agent_done should be yielded; tool_call/tool_result are filtered.
    types = [e["type"] for e in events]
    assert types == ["agent_done"]
    assert events[-1]["text"] == "Final answer."
