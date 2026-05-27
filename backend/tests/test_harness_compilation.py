"""Compilation tests for C/C++ harnesses — verify assertion patterns compile and run."""
import json
import os
import subprocess
import tempfile

from services.exercise_schema import TestCase
from services.assertion_generator import generate_assertions
from test_harnesses import BUILDERS


def _compile_and_run(language: str, solution: str, test_cases: list[TestCase]) -> dict:
    """Build script, compile, run, and return parsed results."""
    assertions = generate_assertions(language, test_cases)
    script = BUILDERS[language](solution, assertions)

    ext = ".cpp" if language == "cpp" else ".c"
    compile_cmd = ["g++", "-std=c++17"] if language == "cpp" else ["gcc"]

    with tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False, encoding="utf-8") as f:
        f.write(script)
        tmp_path = f.name
    bin_path = tmp_path + (".exe" if os.name == "nt" else ".out")

    try:
        compile_result = subprocess.run(
            [*compile_cmd, tmp_path, "-o", bin_path, "-w"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=15,
        )
        if compile_result.returncode != 0:
            return {"all_passed": False, "error": f"Compilation failed: {compile_result.stderr[-200:]}"}

        run_result = subprocess.run(
            [bin_path],
            capture_output=True, encoding="utf-8", errors="replace", timeout=15,
        )
        output = (run_result.stdout or "") + (run_result.stderr or "")

        marker = "__RESULTS__"
        idx = output.find(marker)
        if idx != -1:
            data = json.loads(output[idx + len(marker):].strip())
        else:
            json_start = output.find('{"results":')
            if json_start == -1:
                return {"all_passed": False, "error": "No results in output", "raw": output[-200:]}
            data = json.loads(output[json_start:])

        results = data.get("results", []) if isinstance(data, dict) else data
        all_passed = len(results) > 0 and all(r.get("passed", False) for r in results)
        return {"results": results, "all_passed": all_passed}
    finally:
        for p in (tmp_path, bin_path):
            try:
                os.unlink(p)
            except Exception:
                pass


class TestCppHarness:
    def test_basic_int_comparison(self):
        solution = "int add(int a, int b) { return a + b; }"
        cases = [
            TestCase(name="1+2", input="add(1, 2)", expected="3"),
            TestCase(name="0+0", input="add(0, 0)", expected="0"),
        ]
        result = _compile_and_run("cpp", solution, cases)
        assert result.get("all_passed") is True

    def test_string_comparison_with_equality(self):
        """C++ string assertions use == (not strcmp)."""
        solution = 'std::string greet(std::string name) { return "Hello, " + name; }'
        cases = [
            TestCase(name="alice", input='greet("Alice")', expected='"Hello, Alice"', type="str"),
        ]
        result = _compile_and_run("cpp", solution, cases)
        assert result.get("all_passed") is True

    def test_bool_comparison(self):
        solution = "bool isEven(int n) { return n % 2 == 0; }"
        cases = [
            TestCase(name="even", input="isEven(4)", expected="true"),
            TestCase(name="odd", input="isEven(3)", expected="false"),
        ]
        result = _compile_and_run("cpp", solution, cases)
        assert result.get("all_passed") is True

    def test_negative_values(self):
        solution = "int negate(int n) { return -n; }"
        cases = [
            TestCase(name="neg", input="negate(5)", expected="-5"),
        ]
        result = _compile_and_run("cpp", solution, cases)
        assert result.get("all_passed") is True

    def test_compound_literal_1d_array(self):
        """C++ array argument via compound literal — self-contained input."""
        solution = "int sumArray(int* arr, int size) { int s=0; for(int i=0;i<size;i++) s+=arr[i]; return s; }"
        cases = [
            TestCase(name="sum", input="sumArray((int[]){1, 2, 3, 4, 5}, 5)", expected="15"),
        ]
        result = _compile_and_run("cpp", solution, cases)
        assert result.get("all_passed") is True

    def test_compound_literal_2d_array(self):
        """C++ 2D array argument via compound literal."""
        solution = "int sumMatrix(int m[][4], int rows) { int s=0; for(int i=0;i<rows;i++) for(int j=0;j<4;j++) s+=m[i][j]; return s; }"
        cases = [
            TestCase(name="2x4", input="sumMatrix((int[][4]){{1,2,3,4},{5,6,7,8}}, 2)", expected="36"),
        ]
        result = _compile_and_run("cpp", solution, cases)
        assert result.get("all_passed") is True

    def test_wrong_solution_fails(self):
        solution = "int add(int a, int b) { return a - b; }"
        cases = [
            TestCase(name="1+2", input="add(1, 2)", expected="3"),
        ]
        result = _compile_and_run("cpp", solution, cases)
        assert result.get("all_passed") is False


class TestCHarness:
    def test_basic_int_comparison(self):
        solution = "int add(int a, int b) { return a + b; }"
        cases = [
            TestCase(name="1+2", input="add(1, 2)", expected="3"),
        ]
        result = _compile_and_run("c", solution, cases)
        assert result.get("all_passed") is True

    def test_string_comparison_with_strcmp(self):
        """C string assertions use strcmp."""
        solution = 'const char* greet() { return "hello"; }'
        cases = [
            TestCase(name="hello", input="greet()", expected='"hello"', type="str"),
        ]
        result = _compile_and_run("c", solution, cases)
        assert result.get("all_passed") is True

    def test_compound_literal_1d_array(self):
        """C array argument via compound literal — self-contained input."""
        solution = "int sumArray(int* arr, int size) { int s=0; for(int i=0;i<size;i++) s+=arr[i]; return s; }"
        cases = [
            TestCase(name="sum", input="sumArray((int[]){1, 2, 3, 4, 5}, 5)", expected="15"),
        ]
        result = _compile_and_run("c", solution, cases)
        assert result.get("all_passed") is True

    def test_compound_literal_2d_array(self):
        """C 2D array argument via compound literal."""
        solution = "int sumMatrix(int m[][4], int rows) { int s=0; for(int i=0;i<rows;i++) for(int j=0;j<4;j++) s+=m[i][j]; return s; }"
        cases = [
            TestCase(name="2x4", input="sumMatrix((int[][4]){{1,2,3,4},{5,6,7,8}}, 2)", expected="36"),
        ]
        result = _compile_and_run("c", solution, cases)
        assert result.get("all_passed") is True
