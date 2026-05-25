"""Tests for AI service exercise generation — prompt formatting and JSON parsing."""
import json
import pytest
from services.ai_service import _load_prompt, get_platform_info, parse_exercise_output


def test_prompt_formats_all_languages():
    """Prompt template must format without KeyError for every language."""
    for lang in ["python", "javascript", "typescript", "c", "cpp", "bash"]:
        prompt = _load_prompt("generate_exercise.txt").format(
            language_name=lang,
            topic_title="Test",
            section_title="Test",
            knowledge_description="test",
            content_language="Chinese",
            platform_info=get_platform_info(),
        )
        assert "function_signatures" in prompt
        assert "test_cases" in prompt
        assert "expected" in prompt


def test_parse_exercise_output_valid_json():
    raw = json.dumps({
        "question": "Add two numbers",
        "solution": "def add(a, b):\n    return a + b",
        "function_signatures": [{"name": "add", "params": "a, b", "return_type": ""}],
        "test_cases": [{"name": "basic", "input": "add(1, 2)", "expected": "3"}],
        "knowledge_tags": ["arithmetic"],
        "hints": ["Use + operator"],
    })
    result = parse_exercise_output(raw)
    assert result.question == "Add two numbers"
    assert len(result.test_cases) == 1


def test_parse_exercise_output_with_markdown_wrapper():
    inner = json.dumps({
        "question": "test",
        "solution": "def f(): pass",
        "function_signatures": [{"name": "f", "params": "", "return_type": ""}],
        "test_cases": [{"name": "t", "input": "f()", "expected": "None"}],
        "hints": ["hint"],
    })
    raw = f"```json\n{inner}\n```"
    result = parse_exercise_output(raw)
    assert result.question == "test"


def test_parse_exercise_output_invalid_json_raises():
    with pytest.raises(Exception):
        parse_exercise_output("not json at all {{{")


def test_parse_exercise_output_with_surrounding_text():
    inner = json.dumps({
        "question": "test",
        "solution": "def f(): pass",
        "function_signatures": [{"name": "f", "params": "", "return_type": ""}],
        "test_cases": [{"name": "t", "input": "f()", "expected": "None"}],
        "hints": ["hint"],
    })
    raw = f"Here is the exercise:\n{inner}\nHope that helps!"
    result = parse_exercise_output(raw)
    assert result.question == "test"


def test_parse_exercise_output_with_trailing_commas():
    raw = '{"question":"q","solution":"s","function_signatures":[{"name":"f","params":"","return_type":""}],"test_cases":[{"name":"t","input":"f()","expected":"1",}],"hints":["h",]}'
    result = parse_exercise_output(raw)
    assert result.question == "q"
