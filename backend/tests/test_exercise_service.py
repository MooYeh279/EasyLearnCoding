"""Tests for exercise_service — 5-layer validation pipeline."""
import json
from services.exercise_schema import (
    FunctionSignature, TestCaseSpec, RawExerciseOutput, ValidationResult,
)


def test_layer1_structure_valid():
    from services.exercise_service import validate_exercise_v2

    exercise = RawExerciseOutput(
        question="Add",
        solution="def add(a, b):\n    return a + b",
        function_signatures=[FunctionSignature(name="add", params="a, b", return_type="")],
        test_cases=[
            TestCaseSpec(name="basic", input="add(1, 2)", expected="3"),
        ],
        hints=["hint"],
    )
    result = validate_exercise_v2("python", exercise)
    assert result.layer != "structure"  # should pass structure check


def test_layer2_signature_mismatch():
    from services.exercise_service import validate_exercise_v2

    exercise = RawExerciseOutput(
        question="Add",
        solution="def multiply(a, b):\n    return a * b",
        function_signatures=[FunctionSignature(name="add", params="a, b", return_type="")],
        test_cases=[
            TestCaseSpec(name="basic", input="add(1, 2)", expected="3"),
        ],
        hints=["hint"],
    )
    result = validate_exercise_v2("python", exercise)
    assert result.valid is False
    assert result.layer == "signature"


def test_layer4_run_passes():
    from services.exercise_service import validate_exercise_v2

    exercise = RawExerciseOutput(
        question="Add",
        solution="def add(a, b):\n    return a + b",
        function_signatures=[FunctionSignature(name="add", params="a, b", return_type="")],
        test_cases=[
            TestCaseSpec(name="1+2", input="add(1, 2)", expected="3"),
            TestCaseSpec(name="0+0", input="add(0, 0)", expected="0"),
        ],
        hints=["hint"],
    )
    result = validate_exercise_v2("python", exercise)
    assert result.valid is True
    assert result.test_results is not None
    assert result.test_results["all_passed"] is True


def test_layer4_run_fails_wrong_solution():
    from services.exercise_service import validate_exercise_v2

    exercise = RawExerciseOutput(
        question="Add",
        solution="def add(a, b):\n    return a - b",  # wrong
        function_signatures=[FunctionSignature(name="add", params="a, b", return_type="")],
        test_cases=[
            TestCaseSpec(name="1+2", input="add(1, 2)", expected="3"),
        ],
        hints=["hint"],
    )
    result = validate_exercise_v2("python", exercise)
    assert result.valid is False
    assert result.layer == "run"


def test_build_exercise_script_v2_python():
    from services.exercise_service import build_exercise_script_v2

    cases = [TestCaseSpec(name="basic", input="add(1, 2)", expected="3")]
    script = build_exercise_script_v2(
        "python", "def add(a, b): return a + b", cases,
    )
    assert script is not None
    assert "__test__" in script
    assert "__assert__(add(1, 2) == 3)" in script


def test_run_exercise_code_backward_compat():
    """run_exercise_code supports old-style test_cases with 'assert' key."""
    from services.exercise_service import run_exercise_code

    test_cases = [
        {"name": "basic", "assert": "assert add(1, 1) == 2"},
    ]
    result = run_exercise_code("python", "def add(a, b): return a + b", test_cases)
    assert result["all_passed"] is True


def test_run_exercise_code_new_format():
    """run_exercise_code supports new-style test_cases with 'input'/'expected' keys."""
    from services.exercise_service import run_exercise_code

    test_cases = [
        {"name": "basic", "input": "add(1, 2)", "expected": "3", "is_string": False},
    ]
    result = run_exercise_code("python", "def add(a, b): return a + b", test_cases)
    assert result["all_passed"] is True


def test_parse_test_results_success():
    from services.exercise_service import parse_test_results

    output = '__RESULTS__{"results":[{"name":"test1","passed":true}]}'
    result = parse_test_results(output, 42)
    assert result["all_passed"] is True
    assert result["duration_ms"] == 42


def test_parse_test_results_no_marker():
    from services.exercise_service import parse_test_results

    output = "some output without results marker"
    result = parse_test_results(output, 50)
    assert result["all_passed"] is False
    assert "No test results found" in result["error"]


def test_validate_exercise_backward_compat():
    """Old validate_exercise function still works."""
    from services.exercise_service import validate_exercise

    test_cases = [
        {"name": "basic", "assert": "assert add(1, 1) == 2"},
    ]
    result = validate_exercise("python", "def add(a, b): return a + b", test_cases)
    assert result["all_passed"] is True
