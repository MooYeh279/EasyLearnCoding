import json
import os
import subprocess
import tempfile
import time

from test_harnesses import BUILDERS
from logger import get_logger

logger = get_logger("exercise")


def build_exercise_script(language: str, user_code: str, test_cases: list[dict]) -> str | None:
    """Build a complete runnable script from user code + test assertions.

    Returns the script string, or None if language is unsupported.
    """
    builder = BUILDERS.get(language)
    if not builder:
        return None

    # Convert test case assertions into harness-specific test calls
    test_lines: list[str] = []
    for tc in test_cases:
        name = tc["name"]
        # Escape double-quotes so they don't break generated string literals
        escaped_name = name.replace("\\", "\\\\").replace('"', '\\"')
        assertion = tc["assert"]
        if language == "python":
            # 'assert' is a statement, not usable in lambda bodies.
            # Strip the 'assert ' prefix and use the harness-level __assert__
            # helper which raises AssertionError when the expression is False.
            if assertion.startswith("assert "):
                expr = assertion[7:]
                test_lines.append(f'__test__("{escaped_name}", lambda: __assert__({expr}))')
            else:
                test_lines.append(f'__test__("{escaped_name}", lambda: {assertion})')
        elif language in ("javascript", "typescript"):
            test_lines.append(f'__test__("{escaped_name}", () => {{ {assertion} }})')
        elif language in ("c", "cpp"):
            test_lines.append(f'__TEST__("{escaped_name}", {assertion});')
        elif language == "bash":
            test_lines.append(assertion)  # assertion is already a __test__ call

    test_cases_str = "\n".join(test_lines)
    return builder(user_code, test_cases_str)


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
        # C/C++ harnesses output JSON directly without the marker
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
        # Bash harness outputs a bare array; other harnesses output {"results": [...]}
        if isinstance(parsed, list):
            results = parsed
        else:
            results = parsed.get("results", [])
        # Filter out empty dicts (C/C++/Bash sentinels)
        results = [r for r in results if r and r.get("name")]
        all_passed = all(r.get("passed", False) for r in results)
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


def validate_exercise(language: str, solution: str, test_cases: list[dict]) -> dict:
    """Run reference solution against test cases to validate the exercise.

    Returns the parsed results dict (same format as parse_test_results).
    This is called during exercise generation to ensure the AI-generated
    content is self-consistent before saving.
    """
    script = build_exercise_script(language, solution, test_cases)
    if script is None:
        return {"results": [], "all_passed": False, "error": f"Unsupported language: {language}"}

    start = time.perf_counter()
    try:
        if language == "python":
            result = subprocess.run(
                ["python", "-c", script],
                capture_output=True, text=True, timeout=15,
                cwd=tempfile.gettempdir(),
            )
        elif language in ("javascript", "typescript"):
            node_cmd = "tsx" if language == "typescript" else "node"
            result = subprocess.run(
                [node_cmd, "-e", script],
                capture_output=True, text=True, timeout=15,
                cwd=tempfile.gettempdir(),
            )
        elif language == "c":
            with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
                f.write(script)
                c_path = f.name
            bin_path = c_path + ".exe" if os.name == "nt" else c_path + ".out"
            try:
                compile_result = subprocess.run(
                    ["gcc", c_path, "-o", bin_path, "-w"],
                    capture_output=True, text=True, timeout=15,
                )
                if compile_result.returncode != 0:
                    logger.warning("C compilation failed: %s", compile_result.stderr[-200:])
                    return {
                        "results": [],
                        "all_passed": False,
                        "error": f"Compilation failed: {compile_result.stderr[-200:]}",
                    }
                result = subprocess.run(
                    [bin_path],
                    capture_output=True, text=True, timeout=15,
                    cwd=tempfile.gettempdir(),
                )
            finally:
                os.unlink(c_path)
                if os.path.exists(bin_path):
                    os.unlink(bin_path)
        elif language == "cpp":
            with tempfile.NamedTemporaryFile(mode="w", suffix=".cpp", delete=False) as f:
                f.write(script)
                cpp_path = f.name
            bin_path = cpp_path + ".exe" if os.name == "nt" else cpp_path + ".out"
            try:
                compile_result = subprocess.run(
                    ["g++", cpp_path, "-o", bin_path, "-w"],
                    capture_output=True, text=True, timeout=15,
                )
                if compile_result.returncode != 0:
                    logger.warning("C++ compilation failed: %s", compile_result.stderr[-200:])
                    return {
                        "results": [],
                        "all_passed": False,
                        "error": f"Compilation failed: {compile_result.stderr[-200:]}",
                    }
                result = subprocess.run(
                    [bin_path],
                    capture_output=True, text=True, timeout=15,
                    cwd=tempfile.gettempdir(),
                )
            finally:
                os.unlink(cpp_path)
                if os.path.exists(bin_path):
                    os.unlink(bin_path)
        elif language == "bash":
            result = subprocess.run(
                ["bash", "-c", script],
                capture_output=True, text=True, timeout=15,
                cwd=tempfile.gettempdir(),
            )
        else:
            return {"results": [], "all_passed": False, "error": f"Unsupported language: {language}"}

        duration_ms = int((time.perf_counter() - start) * 1000)
        output = (result.stdout or "") + (result.stderr or "")
        return parse_test_results(output, duration_ms)
    except subprocess.TimeoutExpired:
        return {"results": [], "all_passed": False, "error": "Execution timed out (15s)"}
    except Exception as e:
        return {"results": [], "all_passed": False, "error": str(e)}
