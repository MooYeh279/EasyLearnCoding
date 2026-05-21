import asyncio
from unittest.mock import patch, AsyncMock
from services.ai_service import generate_outline_async, generate_lesson_async

MOCK_OUTLINE = {
    "sections": [
        {
            "title": "Getting Started",
            "description": "Introduction to the topic",
            "lessons": [{"title": "Overview"}, {"title": "Setup"}],
        }
    ]
}

MOCK_LESSON = "## Overview\n\nThis is a lesson about the topic.\n\n```python\nprint('hello')\n```"


@patch("services.ai_service._provider.chat_completion_async")
def test_generate_outline_first_time(mock_chat):
    mock_chat.return_value = '{"sections": [{"title": "Intro", "description": "desc", "lessons": [{"title": "Hello"}]}]}'
    result = asyncio.run(generate_outline_async("Test Topic", "Python"))
    assert "sections" in result
    assert result["sections"][0]["title"] == "Intro"


@patch("services.ai_service._provider.chat_completion_async")
def test_generate_outline_with_feedback(mock_chat):
    mock_chat.return_value = '{"sections": [{"title": "Revised Intro", "description": "new desc", "lessons": [{"title": "Start"}]}]}'
    previous = {"sections": [{"title": "Old", "description": "d", "lessons": []}]}
    result = asyncio.run(generate_outline_async("Topic", "Python", previous_outline=previous, feedback="Make it shorter"))
    assert result["sections"][0]["title"] == "Revised Intro"


@patch("services.ai_service._provider.chat_completion_async")
def test_generate_lesson(mock_chat):
    mock_chat.return_value = "# Lesson Content"
    result = asyncio.run(generate_lesson_async("Topic", "Python", "Section", "Lesson"))
    assert result == "# Lesson Content"


@patch("services.ai_service._provider.chat_completion_async")
def test_generate_outline_with_content_language(mock_chat):
    mock_chat.return_value = '{"sections": [{"title": "Intro", "description": "desc", "lessons": [{"title": "Hello"}]}]}'
    result = asyncio.run(generate_outline_async("Test", "Python", content_language="en"))
    assert result["sections"][0]["title"] == "Intro"
    call_args = mock_chat.call_args
    system_prompt = call_args[1]["messages"][0]["content"]
    assert "English" in system_prompt


@patch("services.ai_service._provider.chat_completion_async")
def test_generate_lesson_with_content_language(mock_chat):
    mock_chat.return_value = "# English Lesson"
    result = asyncio.run(generate_lesson_async("Topic", "Python", "Section", "Lesson", content_language="en"))
    assert result == "# English Lesson"
    call_args = mock_chat.call_args
    system_prompt = call_args[1]["messages"][0]["content"]
    assert "English" in system_prompt
