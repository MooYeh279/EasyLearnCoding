"""Pydantic models for AI exercise output contract and validation results."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TestInput(BaseModel):
    """A single test input expression — AI provides this, system computes expected."""
    name: str = Field(min_length=1)
    input: str = Field(min_length=1)


class TestCase(BaseModel):
    """A complete test case with system-computed expected value and type."""
    name: str = Field(min_length=1)
    input: str = Field(min_length=1)
    expected: str = Field(min_length=1)
    type: str = Field(default="int")  # "str" | "int" | "float" | "bool"


class RawExerciseOutput(BaseModel):
    question: str = Field(min_length=1)
    solution: str = Field(min_length=1)
    test_inputs: list[TestInput] = Field(min_length=1, max_length=10)
    knowledge_tags: list[str] = Field(default_factory=list)
    hints: list[str] = Field(min_length=1)


class ValidationResult(BaseModel):
    valid: bool
    layer: str  # "structure" | "signature" | "compile" | "run"
    error: str = ""
    test_results: dict | None = None
