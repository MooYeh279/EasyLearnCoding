"""Tests for exercise_schema — Pydantic models for AI output contract."""
import pytest
from pydantic import ValidationError


def test_valid_raw_exercise_output():
    from services.exercise_schema import RawExerciseOutput

    data = {
        "question": "Write a function that adds two numbers",
        "solution": "def add(a, b):\n    return a + b",
        "function_signatures": [{"name": "add", "params": "a, b", "return_type": ""}],
        "test_cases": [
            {"name": "basic", "input": "add(1, 2)", "expected": "3"},
            {"name": "zero", "input": "add(0, 0)", "expected": "0"},
        ],
        "knowledge_tags": ["arithmetic"],
        "hints": ["Think about the + operator"],
    }
    result = RawExerciseOutput.model_validate(data)
    assert result.question == "Write a function that adds two numbers"
    assert len(result.test_cases) == 2
    assert result.test_cases[0].input == "add(1, 2)"
    assert result.test_cases[0].expected == "3"
    assert result.test_cases[0].is_string is False
    assert len(result.function_signatures) == 1
    assert result.function_signatures[0].name == "add"


def test_missing_required_field_raises():
    from services.exercise_schema import RawExerciseOutput

    with pytest.raises(ValidationError) as exc_info:
        RawExerciseOutput.model_validate({
            "question": "test",
            # missing solution
            "function_signatures": [{"name": "add", "params": "a, b", "return_type": ""}],
            "test_cases": [{"name": "basic", "input": "add(1,2)", "expected": "3"}],
            "hints": ["hint"],
        })
    assert "solution" in str(exc_info.value)


def test_empty_test_cases_raises():
    from services.exercise_schema import RawExerciseOutput

    with pytest.raises(ValidationError):
        RawExerciseOutput.model_validate({
            "question": "test",
            "solution": "def add(a, b): return a + b",
            "function_signatures": [{"name": "add", "params": "a, b", "return_type": ""}],
            "test_cases": [],
            "hints": ["hint"],
        })


def test_test_case_with_is_string():
    from services.exercise_schema import TestCaseSpec

    tc = TestCaseSpec(name="greet", input="greet()", expected='"hello"', is_string=True)
    assert tc.is_string is True


def test_empty_hints_raises():
    from services.exercise_schema import RawExerciseOutput

    with pytest.raises(ValidationError):
        RawExerciseOutput.model_validate({
            "question": "test",
            "solution": "def f(): pass",
            "function_signatures": [{"name": "f", "params": "", "return_type": ""}],
            "test_cases": [{"name": "t", "input": "f()", "expected": "None"}],
            "hints": [],
        })


def test_declarations_field_default_empty():
    from services.exercise_schema import RawExerciseOutput

    data = {
        "question": "Write a function",
        "solution": "def add(a, b): return a + b",
        "function_signatures": [{"name": "add", "params": "a, b", "return_type": ""}],
        "test_cases": [{"name": "basic", "input": "add(1,2)", "expected": "3"}],
        "hints": ["hint"],
    }
    result = RawExerciseOutput.model_validate(data)
    assert result.declarations == ""


def test_declarations_field_with_enum():
    from services.exercise_schema import RawExerciseOutput

    data = {
        "question": "Check status",
        "solution": "def isActive(s): return s == Status.Active",
        "function_signatures": [{"name": "isActive", "params": "s: Status", "return_type": ": boolean"}],
        "test_cases": [{"name": "active", "input": "isActive(Status.Active)", "expected": "true"}],
        "declarations": "enum Status { Active, Inactive }",
        "hints": ["hint"],
    }
    result = RawExerciseOutput.model_validate(data)
    assert result.declarations == "enum Status { Active, Inactive }"


def test_validation_result_model():
    from services.exercise_schema import ValidationResult

    vr = ValidationResult(valid=False, layer="structure", error="missing field: solution")
    assert vr.valid is False
    assert vr.layer == "structure"
    assert vr.test_results is None

    vr2 = ValidationResult(
        valid=True, layer="run", error="",
        test_results={"results": [{"name": "t1", "passed": True}], "all_passed": True},
    )
    assert vr2.valid is True
    assert vr2.test_results["all_passed"] is True
