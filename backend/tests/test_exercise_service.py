"""Tests for exercise_service — 3-layer validation pipeline."""
from services.exercise_schema import RawExerciseOutput, TestInput


def test_layer2_signature_mismatch():
    from services.exercise_service import validate_exercise

    exercise = RawExerciseOutput(
        question="Implement a Vehicle class with static member count",
        solution="def add(a, b):\n    return a + b",
        test_inputs=[TestInput(name="basic", input="add(1, 2)")],
        hints=["hint"],
    )
    result = validate_exercise("python", exercise)
    assert result.valid is False
    assert result.layer == "signature"


def test_layer3_run_passes():
    from services.exercise_service import validate_exercise

    exercise = RawExerciseOutput(
        question="Implement the add function",
        solution="def add(a, b):\n    return a + b",
        test_inputs=[
            TestInput(name="1+2", input="add(1, 2)"),
            TestInput(name="0+0", input="add(0, 0)"),
        ],
        hints=["hint"],
    )
    result = validate_exercise("python", exercise)
    assert result.valid is True
    assert result.test_results is not None
    assert result.test_results["all_passed"] is True


def test_layer3_run_self_consistency():
    """Auto-computed expected values make any runnable solution pass."""
    from services.exercise_service import validate_exercise

    exercise = RawExerciseOutput(
        question="Implement the add function",
        solution="def add(a, b):\n    return a - b",
        test_inputs=[TestInput(name="1+2", input="add(1, 2)")],
        hints=["hint"],
    )
    result = validate_exercise("python", exercise)
    # With compute_expected, the solution is self-consistent: compute
    # runs add(1,2)->-1, then the run step verifies add(1,2)==-1.
    assert result.valid is True
    assert result.layer == "run"


def test_compute_expected_python():
    from services.exercise_service import compute_expected

    test_cases = compute_expected("python", "def add(a, b):\n    return a + b", [
        {"name": "basic", "input": "add(1, 2)"},
        {"name": "zero", "input": "add(0, 0)"},
    ])
    assert len(test_cases) == 2
    assert test_cases[0]["expected"] == "3"
    assert test_cases[0]["type"] == "int"


def test_run_exercise_code_with_computed():
    from services.exercise_service import run_exercise_code

    test_cases = [
        {"name": "basic", "input": "add(1, 2)", "expected": "3", "type": "int"},
    ]
    result = run_exercise_code("python", "def add(a, b): return a + b", test_cases)
    assert result["all_passed"] is True


def test_compute_expected_string_type():
    from services.exercise_service import compute_expected

    test_cases = compute_expected("python",
        "def greet(n):\n    return f'Hello, {n}'",
        [{"name": "alice", "input": "greet('Alice')"}],
    )
    assert test_cases[0]["type"] == "str"
    assert "Hello" in test_cases[0]["expected"]


def test_compute_expected_bool_type():
    from services.exercise_service import compute_expected

    test_cases = compute_expected("python",
        "def is_even(n):\n    return n % 2 == 0",
        [{"name": "even", "input": "is_even(4)"}],
    )
    assert test_cases[0]["type"] == "bool"
    assert test_cases[0]["expected"] == "True"


def test_build_exercise_script_python():
    from services.exercise_service import build_exercise_script

    cases = [
        {"name": "basic", "input": "add(1, 2)", "expected": "3", "type": "int"},
    ]
    script = build_exercise_script("python", "def add(a, b): return a + b", cases)
    assert script is not None
    assert "__test__" in script
    assert "__assert__(add(1, 2) == 3)" in script


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
