"""Exercise service — 5-layer validation pipeline and code execution."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time

from logger import get_logger
from services.assertion_generator import generate_assertions
from services.exercise_schema import RawExerciseOutput, TestCaseSpec, ValidationResult
from services.template_generator import generate_template, verify_signatures_in_solution
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


def _resolve_lang_config(language: str) -> dict:
    """Resolve language config from code_executor."""
    try:
        from routers.code_executor import _resolve_lang_config as _resolve
        return _resolve(language)
    except Exception:
        return {}


def _is_new_format(test_cases: list[dict]) -> bool:
    """Detect whether test_cases use new format (input/expected) or old format (assert)."""
    if not test_cases:
        return False
    return "input" in test_cases[0] and "expected" in test_cases[0]


def build_exercise_script(language: str, user_code: str, test_cases: list[dict]) -> str | None:
    """Build a complete runnable script. Supports both old and new test case formats."""
    if _is_new_format(test_cases):
        specs = [
            TestCaseSpec(
                name=tc["name"],
                input=tc["input"],
                expected=tc["expected"],
                is_string=tc.get("is_string", False),
            )
            for tc in test_cases
        ]
        return build_exercise_script_v2(language, user_code, specs)

    # Old format: build assertions inline
    builder = BUILDERS.get(language)
    if not builder:
        return None
    test_lines: list[str] = []
    test_fn_counter = 0
    for tc in test_cases:
        name = tc["name"]
        escaped_name = name.replace("\\", "\\\\").replace('"', '\\"')
        assertion = tc["assert"]
        if language == "python":
            if assertion.startswith("assert "):
                expr = assertion[7:]
                test_lines.append(f'__test__("{escaped_name}", lambda: __assert__({expr}))')
            else:
                fn_name = f"__test_fn_{test_fn_counter}"
                test_fn_counter += 1
                lines: list[str] = []
                for line in assertion.split(";"):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if stripped.startswith("assert "):
                        lines.append(f"    __assert__({stripped[7:]})")
                    else:
                        lines.append(f"    {stripped}")
                body = "\n".join(lines)
                test_lines.append(f"def {fn_name}():\n{body}")
                test_lines.append(f'__test__("{escaped_name}", {fn_name})')
        elif language in ("javascript", "typescript"):
            test_lines.append(f'__test__("{escaped_name}", () => {{ {assertion} }})')
        elif language in ("c", "cpp"):
            test_lines.append(f'__TEST__("{escaped_name}", ({assertion}));')
        elif language == "bash":
            test_lines.append(assertion)
    test_cases_str = "\n".join(test_lines)
    return builder(user_code, test_cases_str)


def build_exercise_script_v2(
    language: str, user_code: str, test_cases: list[TestCaseSpec],
) -> str | None:
    """Build a runnable script using new-format test cases and assertion generator."""
    builder = BUILDERS.get(language)
    if not builder:
        return None
    assertions = generate_assertions(language, test_cases)
    if not assertions:
        return None
    return builder(user_code, assertions)


def run_exercise_code(
    language: str, user_code: str, test_cases: list[dict],
) -> dict:
    """Execute user code against test cases. Supports both old and new formats.

    Returns the parsed results dict (same format as parse_test_results).
    """
    script = build_exercise_script(language, user_code, test_cases)
    if script is None:
        return {"results": [], "all_passed": False, "error": f"Unsupported language: {language}"}

    config = _resolve_lang_config(language)
    env = config.get("env", os.environ.copy())
    start = time.perf_counter()
    tmp_path: str | None = None
    bin_path: str | None = None

    try:
        if language == "python":
            result = subprocess.run(
                ["python", "-c", script],
                capture_output=True, encoding="utf-8", errors="replace", timeout=15,
                cwd=tempfile.gettempdir(), env=env,
            )
        elif language in ("javascript", "typescript"):
            node_cmd = config.get("cmd", ["tsx"] if language == "typescript" else ["node"])
            ext = config.get("ext", ".ts" if language == "typescript" else ".js")
            use_shell = config.get("shell", False)
            with tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False, encoding="utf-8") as f:
                f.write(script)
                tmp_path = f.name
            if use_shell:
                result = subprocess.run(
                    f'{" ".join(node_cmd)} "{tmp_path}"',
                    capture_output=True, encoding="utf-8", errors="replace", timeout=15,
                    cwd=tempfile.gettempdir(), env=env, shell=True,
                )
            else:
                result = subprocess.run(
                    [*node_cmd, tmp_path],
                    capture_output=True, encoding="utf-8", errors="replace", timeout=15,
                    cwd=tempfile.gettempdir(), env=env,
                )
        elif language in ("c", "cpp"):
            ext = config.get("ext", ".c" if language == "c" else ".cpp")
            compile_cmd = list(config.get("compile_cmd", ["gcc"] if language == "c" else ["g++", "-std=c++17"]))
            with tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False, encoding="utf-8") as f:
                f.write(script)
                tmp_path = f.name
            bin_path = tmp_path + (".exe" if os.name == "nt" else ".out")
            compile_result = subprocess.run(
                [*compile_cmd, tmp_path, "-o", bin_path, "-w"],
                capture_output=True, encoding="utf-8", errors="replace", timeout=15,
                env=env,
            )
            if compile_result.returncode != 0:
                return {
                    "results": [],
                    "all_passed": False,
                    "error": f"Compilation failed: {compile_result.stderr[-200:]}",
                }
            result = subprocess.run(
                [bin_path],
                capture_output=True, encoding="utf-8", errors="replace", timeout=15,
                cwd=tempfile.gettempdir(),
            )
        elif language == "bash":
            ext = config.get("ext", ".sh")
            with tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False, encoding="utf-8") as f:
                f.write(script)
                tmp_path = f.name
            result = subprocess.run(
                ["bash", tmp_path],
                capture_output=True, encoding="utf-8", errors="replace", timeout=15,
                cwd=tempfile.gettempdir(), env=env,
            )
        else:
            return {"results": [], "all_passed": False, "error": f"Unsupported language: {language}"}

        duration_ms = int((time.perf_counter() - start) * 1000)
        output = (result.stdout or "") + (result.stderr or "")
        parsed = parse_test_results(output, duration_ms)
        if not parsed.get("results") and not parsed.get("all_passed"):
            logger.warning(
                "Execution produced no results. rc=%d stdout=[%s] stderr=[%s]",
                result.returncode,
                (result.stdout or "")[-500:],
                (result.stderr or "")[-500:],
            )
        return parsed
    except subprocess.TimeoutExpired:
        return {"results": [], "all_passed": False, "error": "Execution timed out (15s)"}
    except Exception as e:
        logger.exception("Execution exception: %s", e)
        return {"results": [], "all_passed": False, "error": str(e)}
    finally:
        for path in (tmp_path, bin_path):
            if path:
                try:
                    os.unlink(path)
                except Exception:
                    pass


def validate_exercise_v2(
    language: str, exercise: RawExerciseOutput,
) -> ValidationResult:
    """5-layer validation pipeline.

    Layer 1: Structure (Pydantic) — already validated at parse time
    Layer 2: Signature consistency — function_signatures match solution
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

    # Layer 3+4: Compile and run
    test_dicts = [tc.model_dump() for tc in exercise.test_cases]
    run_result = run_exercise_code(language, exercise.solution, test_dicts)

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

    # Layer 5: Template validation
    template = generate_template(language, exercise.function_signatures)
    if template:
        template_run = run_exercise_code(language, template, test_dicts)
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


# Backward-compatible alias for old code paths
def validate_exercise(language: str, solution: str, test_cases: list[dict]) -> dict:
    """Run reference solution against test cases (backward-compatible entry point)."""
    return run_exercise_code(language, solution, test_cases)
