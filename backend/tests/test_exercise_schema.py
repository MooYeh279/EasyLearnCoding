"""Tests for exercise_schema — Pydantic models for new AI output contract."""
import pytest
from pydantic import ValidationError


def test_valid_raw_exercise_output():
    from services.exercise_schema import RawExerciseOutput

    data = {
        "question": "Write a function that adds two numbers",
        "solution": "def add(a, b):\n    return a + b",
        "test_inputs": [
            {"name": "basic", "input": "add(1, 2)"},
            {"name": "zero", "input": "add(0, 0)"},
        ],
        "knowledge_tags": ["arithmetic"],
        "hints": ["Think about the + operator"],
    }
    result = RawExerciseOutput.model_validate(data)
    assert result.question == "Write a function that adds two numbers"
    assert len(result.test_inputs) == 2
    assert result.test_inputs[0].input == "add(1, 2)"
    assert result.test_inputs[0].name == "basic"


def test_missing_required_field_raises():
    from services.exercise_schema import RawExerciseOutput

    with pytest.raises(ValidationError):
        RawExerciseOutput.model_validate({
            "question": "test",
            "test_inputs": [{"name": "basic", "input": "add(1,2)"}],
            "hints": ["hint"],
        })


def test_empty_test_inputs_raises():
    from services.exercise_schema import RawExerciseOutput

    with pytest.raises(ValidationError):
        RawExerciseOutput.model_validate({
            "question": "test",
            "solution": "def add(a, b): return a + b",
            "test_inputs": [],
            "hints": ["hint"],
        })


def test_empty_hints_raises():
    from services.exercise_schema import RawExerciseOutput

    with pytest.raises(ValidationError):
        RawExerciseOutput.model_validate({
            "question": "test",
            "solution": "def f(): pass",
            "test_inputs": [{"name": "t", "input": "f()"}],
            "hints": [],
        })


def test_test_case_model():
    from services.exercise_schema import TestCase

    tc = TestCase(name="basic", input="add(1, 2)", expected="3", type="int")
    assert tc.type == "int"
    assert tc.expected == "3"


def test_test_input_model():
    from services.exercise_schema import TestInput

    ti = TestInput(name="basic", input="add(1, 2)")
    assert ti.name == "basic"
    assert ti.input == "add(1, 2)"


def test_validation_result_model():
    from services.exercise_schema import ValidationResult

    vr = ValidationResult(valid=True, layer="run", error="",
                          test_results={"results": [], "all_passed": True})
    assert vr.valid is True
    assert vr.test_results["all_passed"] is True
