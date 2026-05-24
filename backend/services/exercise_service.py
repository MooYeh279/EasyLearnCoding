import json
import os
import subprocess
import tempfile
import time

from test_harnesses import BUILDERS
from logger import get_logger

logger = get_logger("exercise")


def _python_assert_body(assertion: str) -> str:
    """Convert a multi-statement assertion string to Python def-body lines.

    Replaces bare ``assert expr`` with ``__assert__(expr)`` and indents
    each line so the result can be pasted inside a ``def …():`` block.
    """
    lines: list[str] = []
    for line in assertion.split(";"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("assert "):
            lines.append(f"    __assert__({stripped[7:]})")
        else:
            lines.append(f"    {stripped}")
    return "\n".join(lines)


def build_exercise_script(language: str, user_code: str, test_cases: list[dict]) -> str | None:
    """Build a complete runnable script from user code + test assertions.

    Returns the script string, or None if language is unsupported.
    """
    builder = BUILDERS.get(language)
    if not builder:
        return None

    # Convert test case assertions into harness-specific test calls
    test_lines: list[str] = []
    test_fn_counter = 0
    for tc in test_cases:
        name = tc["name"]
        # Escape double-quotes so they don't break generated string literals
        escaped_name = name.replace("\\", "\\\\").replace('"', '\\"')
        assertion = tc["assert"]
        if language == "python":
            # 'assert' is a statement in Python and cannot appear inside a
            # lambda body.  Two cases:
            #   1. Simple: "assert expr"            → lambda: __assert__(expr)
            #   2. Complex: setup + assert expr     → def wrapper(): … setup … __assert__(expr)
            if assertion.startswith("assert "):
                expr = assertion[7:]
                test_lines.append(f'__test__("{escaped_name}", lambda: __assert__({expr}))')
            else:
                # Multi-statement: wrap in a local def so the harness can call it
                fn_name = f"__test_fn_{test_fn_counter}"
                test_fn_counter += 1
                body = _python_assert_body(assertion)
                test_lines.append(f"def {fn_name}():\n{body}")
                test_lines.append(f'__test__("{escaped_name}", {fn_name})')
        elif language in ("javascript", "typescript"):
            test_lines.append(f'__test__("{escaped_name}", () => {{ {assertion} }})')
        elif language in ("c", "cpp"):
            # Wrap in () so commas inside brace-initializers like
            # std::map<int,int>{{1,2},{3,4}} don't split the macro argument
            test_lines.append(f'__TEST__("{escaped_name}", ({assertion}));')
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
    """Resolve language config, delegating to code_executor's implementation.

    Returns a dict with env, shell, cmd, ext, compile_cmd, etc.
    Matching the lesson code execution flow exactly.
    """
    try:
        from routers.code_executor import _resolve_lang_config as _resolve
        return _resolve(language)
    except Exception:
        return {}


def validate_exercise(language: str, solution: str, test_cases: list[dict]) -> dict:
    """Run reference solution against test cases to validate the exercise.

    Returns the parsed results dict (same format as parse_test_results).
    Uses the same language config resolution as code_executor for consistent
    execution behavior (PATH, shell mode, compile commands, etc.).
    """
    script = build_exercise_script(language, solution, test_cases)
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
                lang_label = "C" if language == "c" else "C++"
                logger.warning("%s compilation failed: %s", lang_label, compile_result.stderr[-200:])
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
            use_shell = config.get("shell", False)
            ext = config.get("ext", ".sh")
            with tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False, encoding="utf-8") as f:
                f.write(script)
                tmp_path = f.name
            if use_shell:
                bash_cmd = config.get("cmd", ["bash"])
                result = subprocess.run(
                    f'{" ".join(bash_cmd)} "{tmp_path}"',
                    capture_output=True, encoding="utf-8", errors="replace", timeout=15,
                    cwd=tempfile.gettempdir(), env=env, shell=True,
                )
            else:
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
                "Validation produced no results. rc=%d stdout=[%s] stderr=[%s]",
                result.returncode,
                (result.stdout or "")[-500:],
                (result.stderr or "")[-500:],
            )
            # Log the first 500 chars of stderr too — TransformError messages
            # can appear at the beginning and get truncated by the -500 slice
            if result.stderr and len(result.stderr) > 500:
                logger.warning(
                    "stderr (first 500 chars): [%s]",
                    result.stderr[:500],
                )
        return parsed
    except subprocess.TimeoutExpired:
        return {"results": [], "all_passed": False, "error": "Execution timed out (15s)"}
    except Exception as e:
        logger.exception("Validation exception: %s", e)
        return {"results": [], "all_passed": False, "error": str(e)}
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        if bin_path:
            try:
                os.unlink(bin_path)
            except Exception:
                pass
