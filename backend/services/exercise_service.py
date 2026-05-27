"""Exercise service — validation pipeline with auto-computed expected values."""
from __future__ import annotations

import json

from logger import get_logger
from services.assertion_generator import generate_assertions
from services.exercise_schema import TestInput, TestCase, RawExerciseOutput, ValidationResult
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


def compute_expected(language: str, solution: str, test_inputs: list[dict]) -> list[dict]:
    """Run solution against test_inputs and return complete test cases.

    Each input dict must have 'name' and 'input'.
    Returns list of dicts with: name, input, expected, type.
    """
    from test_harnesses.compute_scripts import BUILDERS as COMPUTE_BUILDERS
    from services.code_runner import execute_code

    builder = COMPUTE_BUILDERS.get(language)
    if not builder:
        raise ValueError(f"Unsupported language for compute: {language}")

    script = builder(solution, test_inputs)
    result = execute_code(
        language, script,
        timeout=15,
        suppress_warnings=True,
        native=True,
    )

    if result.error and result.error.startswith("Compilation failed"):
        raise ValueError(f"Compute script compilation failed: {result.error[-200:]}")

    output = result.stdout + result.stderr
    parsed = _parse_compute_results(output)
    if not parsed:
        raise ValueError(f"Compute produced no results. stdout=[{output[-200:]}]")

    test_cases = []
    for ti, computed in zip(test_inputs, parsed):
        test_cases.append({
            "name": ti["name"],
            "input": ti["input"],
            "expected": computed["value"],
            "type": computed.get("type", "int"),
        })
    return test_cases


def _parse_compute_results(output: str) -> list[dict] | None:
    """Parse __RESULTS__[...] from compute script output."""
    marker = "__RESULTS__"
    idx = output.find(marker)
    if idx == -1:
        return None
    json_str = output[idx + len(marker):].strip()
    json_str = _extract_json(json_str, 0)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        logger.warning("Failed to parse compute results JSON")
        return None


def _extract_func_names_from_solution(solution: str, language: str) -> list[str]:
    """Extract function/class/method names from solution code."""
    import re
    names = []
    if language == "python":
        for m in re.finditer(r'(?:def|class)\s+(\w+)', solution):
            names.append(m.group(1))
    elif language == "bash":
        for m in re.finditer(r'(?:function\s+)?(\w+)\s*\(\)', solution):
            names.append(m.group(1))
    elif language in ("c", "cpp"):
        for m in re.finditer(r'\w[\w\s*&:<>]*\s+(\w+)\s*\([^)]*\)\s*\{', solution):
            name = m.group(1)
            if name not in ("if", "for", "while", "switch", "main"):
                names.append(name)
    elif language in ("javascript", "typescript"):
        for m in re.finditer(r'(?:function|class)\s+(\w+)', solution):
            names.append(m.group(1))
        for m in re.finditer(r'(?<!function\s)(?<!\w)(\w+)\s*\([^)]*\)\s*\{', solution):
            name = m.group(1)
            if name not in ("if", "for", "while", "switch", "catch"):
                if name not in names:
                    names.append(name)
    return names


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

    test_cases must be dicts with keys: name, input, expected, type.
    """
    builder = BUILDERS.get(language)
    if not builder:
        return None

    specs = [
        TestCase(
            name=tc["name"],
            input=tc["input"],
            expected=tc["expected"],
            type=tc.get("type", "int"),
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
    """
    script = build_exercise_script(language, user_code, test_cases)
    if script is None:
        return {"results": [], "all_passed": False, "error": f"Unsupported language: {language}"}

    from services.code_runner import execute_code

    result = execute_code(
        language, script,
        timeout=15,
        suppress_warnings=True,
        native=True,
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
    """3-layer validation pipeline.

    Layer 1: Structure (Pydantic) — already validated at parse time
    Layer 2: Signature — function names from solution appear in question
    Layer 3: Compute & Run — compute expected via solution execution,
             then verify solution passes all test cases
    """
    # Layer 2: Signature — extract function names from solution
    func_names = _extract_func_names_from_solution(exercise.solution, language)
    if not func_names:
        return ValidationResult(
            valid=False,
            layer="signature",
            error="No function/class definitions found in solution",
        )

    names_in_question = [name for name in func_names if name in exercise.question]
    if not names_in_question:
        return ValidationResult(
            valid=False,
            layer="signature",
            error=f"None of the function names {func_names} appear in the question",
        )

    # Layer 3: Compute expected values, then run assertions
    input_dicts = [{"name": ti.name, "input": ti.input} for ti in exercise.test_inputs]
    test_cases = compute_expected(language, exercise.solution, input_dicts)
    run_result = run_exercise_code(language, exercise.solution, test_cases, label="solution")

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

    return ValidationResult(
        valid=True,
        layer="run",
        error="",
        test_results=run_result,
    )
