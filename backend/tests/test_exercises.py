"""Tests for exercise_service — build, parse, validate across languages."""
import json
from services.exercise_service import build_exercise_script, parse_test_results


def test_generate_exercise_prompt_formats_all_languages():
    """Regression: prompt template must format without KeyError for every language."""
    from services.ai_service import _load_prompt, _assertion_syntax_for, get_platform_info

    for lang in ["python", "javascript", "typescript", "c", "cpp", "bash"]:
        prompt = _load_prompt("generate_exercise.txt").format(
            language_name=lang,
            topic_title="Test",
            section_title="Test",
            knowledge_description="test",
            content_language="Chinese",
            platform_info=get_platform_info(),
            assertion_syntax=_assertion_syntax_for(lang),
        )
        assert "{assertion_code}" in prompt
        assert _assertion_syntax_for(lang) in prompt


def test_build_python_script():
    test_cases = [
        {"name": "1+1", "assert": "assert add(1, 1) == 2"},
        {"name": "2+3", "assert": "assert add(2, 3) == 5"},
    ]
    script = build_exercise_script(
        "python",
        "def add(a, b): return a + b",
        test_cases,
    )
    assert script is not None
    assert "def add" in script
    assert "__test__" in script
    assert "__RESULTS__" in script
    assert "__assert__(add(1, 1) == 2)" in script


def test_build_javascript_script():
    test_cases = [
        {"name": "1+1", "assert": "console.assert(add(1, 1) === 2)"},
    ]
    script = build_exercise_script(
        "javascript",
        "function add(a, b) { return a + b; }",
        test_cases,
    )
    assert script is not None
    assert "function add" in script
    assert "__test__" in script


def test_build_unsupported_language():
    script = build_exercise_script("rust", "fn main() {}", [])
    assert script is None


def test_parse_test_results_success():
    output = 'some stdout\n__RESULTS__{"results":[{"name":"test1","passed":true},{"name":"test2","passed":true}]}'
    result = parse_test_results(output, 42)
    assert result["all_passed"] is True
    assert len(result["results"]) == 2
    assert result["duration_ms"] == 42


def test_parse_test_results_partial_failure():
    output = '__RESULTS__{"results":[{"name":"test1","passed":true},{"name":"test2","passed":false,"error":"boom"}]}'
    result = parse_test_results(output, 100)
    assert result["all_passed"] is False
    assert result["results"][1]["error"] == "boom"


def test_parse_test_results_no_marker():
    output = "some output without results marker"
    result = parse_test_results(output, 50)
    assert result["all_passed"] is False
    assert "No test results found" in result["error"]


def test_parse_test_results_malformed_json():
    output = "__RESULTS__not json here"
    result = parse_test_results(output, 50)
    assert result["all_passed"] is False
    assert "Failed to parse" in result["error"]


def test_exercise_service_python_validation_basic():
    """End-to-end: build a Python script with correct code, verify it passes."""
    from services.exercise_service import validate_exercise

    test_cases = [
        {"name": "basic add", "assert": "assert add(1, 1) == 2"},
        {"name": "zero add", "assert": "assert add(0, 5) == 5"},
    ]
    solution = "def add(a, b):\n    return a + b"
    result = validate_exercise("python", solution, test_cases)
    assert result["all_passed"] is True, f"Expected all passed, got: {result}"
    assert len(result["results"]) == 2


def test_exercise_service_python_validation_failure():
    """End-to-end: incorrect code should fail."""
    from services.exercise_service import validate_exercise

    test_cases = [
        {"name": "should fail", "assert": "assert add(1, 1) == 3"},
    ]
    solution = "def add(a, b):\n    return a + b"
    result = validate_exercise("python", solution, test_cases)
    assert result["all_passed"] is False
