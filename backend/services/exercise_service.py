"""Exercise service — 5-layer validation pipeline and code execution."""
from __future__ import annotations

import json

from logger import get_logger
from services.assertion_generator import generate_assertions
from services.exercise_schema import RawExerciseOutput, TestCaseSpec, ValidationResult
from services.template_generator import generate_template_from_solution, verify_signatures_in_solution
from test_harnesses import BUILDERS

logger = get_logger("exercise")


def _extract_json(text: str, start: int) -> str:
    """Extract a balanced JSON object/array from text starting at start index."""
    i = start
    depth = 0
    in_string = False
    escape = False
    while i < len(text):
        ch = text[i]
        if escape:
            escape = False
            i += 1
            continue
        if ch == "\\":
            escape = True
        elif ch == '"' and not escape:
            in_string = not in_string
        elif not in_string:
            if ch in ("{", "["):
                depth += 1
            elif ch in ("}", "]"):
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        i += 1
    return text[start:]


def parse_test_results(output: str, duration_ms: int) -> dict:
    """Parse __RESULTS__ JSON from script output.

    Supports two output formats:
    1. __RESULTS__<json> (Python, JavaScript, Bash)
    2. Raw {"results": [...]} in stdout (C, C++)

    Returns the full results dict with metadata.
    """
    marker = "__RESULTS__"
    idx = output.find(marker)
    if idx != -1:
        raw = output[idx + len(marker):].strip()
        json_str = _extract_json(raw, 0)
    else:
        json_start = output.find('{"results":')
        if json_start == -1:
            return {
                "results": [],
                "all_passed": False,
                "error": "No test results found in output",
                "duration_ms": duration_ms,
                "raw_output": output[-500:],
            }
        json_str = _extract_json(output, json_start)

    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, list):
            results = parsed
        else:
            results = parsed.get("results", [])
        results = [r for r in results if r and r.get("name")]
        all_passed = len(results) > 0 and all(r.get("passed", False) for r in results)
        return {
            "results": results,
            "all_passed": all_passed,
            "duration_ms": duration_ms,
        }
    except json.JSONDecodeError:
        logger.warning("Failed to parse test results JSON")
        return {
            "results": [],
            "all_passed": False,
            "error": "Failed to parse test results",
            "duration_ms": duration_ms,
            "raw_output": output[-500:],
        }


def build_exercise_script(language: str, user_code: str, test_cases: list[dict]) -> str | None:
    """Build a complete runnable script from user code and test cases.

    test_cases must be dicts with keys: name, input, expected, is_string (optional).
    """
    builder = BUILDERS.get(language)
    if not builder:
        return None

    specs = [
        TestCaseSpec(
            name=tc["name"],
            input=tc["input"],
            expected=tc["expected"],
            is_string=tc.get("is_string", False),
        )
        for tc in test_cases
    ]
    assertions = generate_assertions(language, specs)
    if not assertions:
        return None
    return builder(user_code, assertions)


def run_exercise_code(
    language: str, user_code: str, test_cases: list[dict],
    *, label: str = "user",
) -> dict:
    """Execute user code against test cases.

    Returns the parsed results dict (same format as parse_test_results).
    *label* is used in log messages to distinguish solution validation
    from template validation ("solution" / "template" / "user").
    """
    script = build_exercise_script(language, user_code, test_cases)
    if script is None:
        return {"results": [], "all_passed": False, "error": f"Unsupported language: {language}"}

    from services.code_runner import execute_code

    result = execute_code(
        language, script,
        timeout=15,
        suppress_warnings=True,  # Exercise validation: suppress compiler warnings
        native=True,  # Exercise harnesses are written in the target language
    )

    duration_ms = result.duration_ms

    if result.error and result.error.startswith("Compilation failed"):
        return {"results": [], "all_passed": False, "error": result.error}

    output = result.stdout + result.stderr
    parsed = parse_test_results(output, duration_ms)
    if not parsed.get("results") and not parsed.get("all_passed"):
        logger.warning(
            "[%s] Execution produced no results. rc=%d stdout=[%s] stderr=[%s]",
            label, result.exit_code,
            result.stdout[-500:],
            result.stderr[-500:],
        )
    return parsed



def validate_exercise(
    language: str, exercise: RawExerciseOutput,
) -> ValidationResult:
    """5-layer validation pipeline.

    Layer 1: Structure (Pydantic) — already validated at parse time
    Layer 2: Signature consistency — function_signatures match solution AND question
    Layer 3: Compile — solution compiles/parses
    Layer 4: Run — solution passes all test cases
    Layer 5: Template — generated template is syntactically valid
    """
    # Layer 2: Signature consistency
    if not verify_signatures_in_solution(exercise.function_signatures, exercise.solution):
        missing = [s.name for s in exercise.function_signatures if s.name not in exercise.solution]
        return ValidationResult(
            valid=False,
            layer="signature",
            error=f"Function names not found in solution: {', '.join(missing)}",
        )

    # Check that function/class names from signatures appear in the question
    sig_names = [s.name for s in exercise.function_signatures]
    names_in_question = [name for name in sig_names if name in exercise.question]
    if not names_in_question:
        return ValidationResult(
            valid=False,
            layer="signature",
            error=f"None of the function names {sig_names} appear in the question",
        )

    # Layer 3: Compile and run
    test_dicts = [tc.model_dump() for tc in exercise.test_cases]
    run_result = run_exercise_code(language, exercise.solution, test_dicts, label="solution")

    if run_result.get("error", "").startswith("Compilation failed"):
        return ValidationResult(
            valid=False,
            layer="compile",
            error=run_result["error"],
        )

    if not run_result.get("all_passed"):
        failed = [r for r in run_result.get("results", []) if not r.get("passed")]
        error_detail = "; ".join(
            f"{f['name']}: {f.get('error', 'test failed')}" for f in failed
        ) if failed else run_result.get("error", "unknown")
        return ValidationResult(
            valid=False,
            layer="run",
            error=error_detail,
            test_results=run_result,
        )

    # Layer 6: Template validation
    template = generate_template_from_solution(exercise.solution, language)
    if template:
        template_run = run_exercise_code(language, template, test_dicts, label="template")
        if template_run.get("error", "").startswith("Compilation failed"):
            return ValidationResult(
                valid=False,
                layer="template",
                error=f"Generated template has syntax error: {template_run['error']}",
            )

    return ValidationResult(
        valid=True,
        layer="run",
        error="",
        test_results=run_result,
    )
