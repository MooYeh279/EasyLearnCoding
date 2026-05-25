"""Tests for exercise_service — 6-layer validation pipeline."""
import json
from services.exercise_schema import (
    FunctionSignature, TestCaseSpec, RawExerciseOutput, ValidationResult,
)


def test_layer1_structure_valid():
    from services.exercise_service import validate_exercise

    exercise = RawExerciseOutput(
        question="Implement the add function",
        solution="def add(a, b):\n    return a + b",
        function_signatures=[FunctionSignature(name="add", params="a, b", return_type="")],
        test_cases=[
            TestCaseSpec(name="basic", input="add(1, 2)", expected="3"),
        ],
        hints=["hint"],
    )
    result = validate_exercise("python", exercise)
    assert result.layer != "structure"


def test_layer2_signature_mismatch():
    from services.exercise_service import validate_exercise

    exercise = RawExerciseOutput(
        question="Implement the add function",
        solution="def multiply(a, b):\n    return a * b",
        function_signatures=[FunctionSignature(name="add", params="a, b", return_type="")],
        test_cases=[
            TestCaseSpec(name="basic", input="add(1, 2)", expected="3"),
        ],
        hints=["hint"],
    )
    result = validate_exercise("python", exercise)
    assert result.valid is False
    assert result.layer == "signature"


def test_layer2_question_signature_mismatch():
    """Function names from signatures must appear in the question text."""
    from services.exercise_service import validate_exercise

    exercise = RawExerciseOutput(
        question="Implement a Vehicle class with static member count",
        solution="def add(a, b):\n    return a + b",
        function_signatures=[FunctionSignature(name="add", params="a, b", return_type="")],
        test_cases=[
            TestCaseSpec(name="basic", input="add(1, 2)", expected="3"),
        ],
        hints=["hint"],
    )
    result = validate_exercise("python", exercise)
    assert result.valid is False
    assert result.layer == "signature"
    assert "question" in result.error.lower() or "add" in result.error


def test_layer5_run_passes():
    from services.exercise_service import validate_exercise

    exercise = RawExerciseOutput(
        question="Implement the add function",
        solution="def add(a, b):\n    return a + b",
        function_signatures=[FunctionSignature(name="add", params="a, b", return_type="")],
        test_cases=[
            TestCaseSpec(name="1+2", input="add(1, 2)", expected="3"),
            TestCaseSpec(name="0+0", input="add(0, 0)", expected="0"),
        ],
        hints=["hint"],
    )
    result = validate_exercise("python", exercise)
    assert result.valid is True
    assert result.test_results is not None
    assert result.test_results["all_passed"] is True


def test_layer5_run_fails_wrong_solution():
    from services.exercise_service import validate_exercise

    exercise = RawExerciseOutput(
        question="Implement the add function",
        solution="def add(a, b):\n    return a - b",
        function_signatures=[FunctionSignature(name="add", params="a, b", return_type="")],
        test_cases=[
            TestCaseSpec(name="1+2", input="add(1, 2)", expected="3"),
        ],
        hints=["hint"],
    )
    result = validate_exercise("python", exercise)
    assert result.valid is False
    assert result.layer == "run"


def test_build_exercise_script_python():
    from services.exercise_service import build_exercise_script

    cases = [TestCaseSpec(name="basic", input="add(1, 2)", expected="3")]
    script = build_exercise_script(
        "python", "def add(a, b): return a + b",
        [tc.model_dump() for tc in cases],
    )
    assert script is not None
    assert "__test__" in script
    assert "__assert__(add(1, 2) == 3)" in script


def test_run_exercise_code_python():
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


def test_validate_exercise_with_declarations():
    from services.exercise_service import validate_exercise

    exercise = RawExerciseOutput(
        question="Check if the status is active using is_active",
        solution="def is_active(s):\n    return s == 'active'",
        function_signatures=[FunctionSignature(name="is_active", params="s", return_type="")],
        test_cases=[
            TestCaseSpec(name="active", input="is_active('active')", expected="True"),
        ],
        declarations="",
        hints=["hint"],
    )
    result = validate_exercise("python", exercise)
    assert result.valid is True


def test_build_exercise_script_bash():
    from services.exercise_service import build_exercise_script

    cases = [TestCaseSpec(name="basic", input="add 1 2", expected="3")]
    script = build_exercise_script(
        "bash", "add() { echo $(( $1 + $2 )); }",
        [tc.model_dump() for tc in cases],
    )
    assert script is not None
    assert "__test__" in script
    assert "add 1 2" in script


def test_run_exercise_code_bash():
    from services.exercise_service import run_exercise_code

    test_cases = [
        {"name": "basic", "input": "add 1 2", "expected": "3", "is_string": False},
    ]
    result = run_exercise_code("bash", "add() { echo $(( $1 + $2 )); }", test_cases)
    assert result["all_passed"] is True


def test_run_exercise_code_bash_string_output():
    from services.exercise_service import run_exercise_code

    test_cases = [
        {"name": "greet", "input": "greet Alice", "expected": "hello Alice", "is_string": True},
    ]
    result = run_exercise_code("bash", 'greet() { echo "hello $1"; }', test_cases)
    assert result["all_passed"] is True
