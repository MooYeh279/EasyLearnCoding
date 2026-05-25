"""Pydantic models for AI exercise output contract and validation results."""
from __future__ import annotations

from pydantic import BaseModel, Field


class FunctionSignature(BaseModel):
    name: str = Field(min_length=1)
    params: str = ""
    return_type: str = ""


class TestCaseSpec(BaseModel):
    name: str = Field(min_length=1)
    input: str = Field(min_length=1)
    expected: str = Field(min_length=1)
    is_string: bool = False


class RawExerciseOutput(BaseModel):
    question: str = Field(min_length=1)
    solution: str = Field(min_length=1)
    function_signatures: list[FunctionSignature] = Field(min_length=1)
    test_cases: list[TestCaseSpec] = Field(min_length=1, max_length=10)
    knowledge_tags: list[str] = Field(default_factory=list)
    hints: list[str] = Field(min_length=1)


class ValidationResult(BaseModel):
    valid: bool
    layer: str  # "structure" | "signature" | "compile" | "run" | "template"
    error: str = ""
    test_results: dict | None = None
