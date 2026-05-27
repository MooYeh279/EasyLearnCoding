"""Tests for AI service exercise generation — prompt formatting and JSON parsing."""
import json
import pytest
from services.ai_service import _load_prompt, get_platform_info, _get_language_note, parse_exercise_output


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
            language_note=_get_language_note(lang),
        )
        assert "test_inputs" in prompt


def test_parse_exercise_output_valid_json():
    raw = json.dumps({
        "question": "Add two numbers",
        "solution": "def add(a, b):\n    return a + b",
        "test_inputs": [{"name": "basic", "input": "add(1, 2)"}],
        "knowledge_tags": ["arithmetic"],
        "hints": ["Use + operator"],
    })
    result = parse_exercise_output(raw)
    assert result.question == "Add two numbers"
    assert len(result.test_inputs) == 1


def test_parse_exercise_output_with_markdown_wrapper():
    inner = json.dumps({
        "question": "test",
        "solution": "def f(): pass",
        "test_inputs": [{"name": "t", "input": "f()"}],
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
        "test_inputs": [{"name": "t", "input": "f()"}],
        "hints": ["hint"],
    })
    raw = f"Here is the exercise:\n{inner}\nHope that helps!"
    result = parse_exercise_output(raw)
    assert result.question == "test"


def test_parse_exercise_output_with_trailing_commas():
    raw = '{"question":"q","solution":"s","test_inputs":[{"name":"t","input":"f()"}],"hints":["h",]}'
    result = parse_exercise_output(raw)
    assert result.question == "q"


class TestCellsToText:
    """Tests for _cells_to_text and _build_knowledge_summary in exercises router."""

    def test_plain_text_passthrough(self):
        from routers.exercises import _cells_to_text
        assert _cells_to_text("hello world") == "hello world"

    def test_empty_string(self):
        from routers.exercises import _cells_to_text
        assert _cells_to_text("") == ""

    def test_json_cells_markdown_only(self):
        from routers.exercises import _cells_to_text
        cells = json.dumps([
            {"id": "a1", "type": "markdown", "content": "# Intro\nSome text"},
            {"id": "a2", "type": "markdown", "content": "## Details"},
        ])
        result = _cells_to_text(cells)
        assert "# Intro\nSome text" in result
        assert "## Details" in result

    def test_json_cells_mixed(self):
        from routers.exercises import _cells_to_text
        cells = json.dumps([
            {"id": "a1", "type": "markdown", "content": "Here is code:"},
            {"id": "a2", "type": "code", "language": "python", "code": "print(1)", "output": None},
        ])
        result = _cells_to_text(cells)
        assert "Here is code:" in result
        assert "```python" in result
        assert "print(1)" in result

    def test_invalid_json_fallback(self):
        from routers.exercises import _cells_to_text
        assert _cells_to_text("[broken json") == "[broken json"


class TestBuildKnowledgeSummary:
    def test_extracts_cell_content(self):
        from routers.exercises import _build_knowledge_summary

        class FakeLesson:
            def __init__(self, title, content):
                self.title = title
                self.content = content

        cells = json.dumps([
            {"id": "a1", "type": "markdown", "content": "Key concept: closures"},
            {"id": "a2", "type": "code", "language": "python", "code": "def outer():\n    x=1", "output": None},
        ])
        lessons = [FakeLesson("Closures", cells)]
        result = _build_knowledge_summary(lessons)
        assert "# Closures" in result
        assert "Key concept: closures" in result
        assert "```python" in result
