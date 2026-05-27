"""Tests for compute_scripts — per-language expected value computation."""
import json
import pytest
from test_harnesses.compute_scripts import BUILDERS


def _run_compute(language: str, solution: str, inputs: list[dict]) -> list[dict]:
    """Run compute script and return parsed results."""
    from services.code_runner import execute_code

    script = BUILDERS[language](solution, inputs)
    result = execute_code(language, script, timeout=15,
                          suppress_warnings=True, native=True)

    if result.error:
        pytest.fail(
            f"Compute failed: {result.error}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    output = result.stdout + result.stderr
    marker = "__RESULTS__"
    idx = output.find(marker)
    assert idx != -1, f"No __RESULTS__ in output: {output[-300:]}"
    json_str = output[idx + len(marker):].strip()
    # Extract balanced JSON array
    i = 0
    depth = 0
    while i < len(json_str):
        ch = json_str[i]
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                json_str = json_str[:i + 1]
                break
        i += 1
    return json.loads(json_str)


class TestPythonCompute:
    def test_int_return(self):
        results = _run_compute("python", "def add(a, b):\n    return a + b", [
            {"name": "basic", "input": "add(1, 2)"},
            {"name": "zero", "input": "add(0, 0)"},
        ])
        assert len(results) == 2
        assert results[0]["name"] == "basic"
        assert results[0]["value"] == "3"
        assert results[0]["type"] == "int"

    def test_str_return(self):
        results = _run_compute("python",
            "def greet(n):\n    return f'Hello, {n}'",
            [{"name": "alice", "input": "greet('Alice')"}],
        )
        assert results[0]["type"] == "str"
        assert "Hello" in results[0]["value"]

    def test_bool_return(self):
        results = _run_compute("python",
            "def is_even(n):\n    return n % 2 == 0",
            [{"name": "even", "input": "is_even(4)"}],
        )
        assert results[0]["type"] == "bool"
        assert results[0]["value"] == "True"


class TestJSCompute:
    def test_int_return(self):
        results = _run_compute("javascript",
            "function add(a, b) { return a + b; }",
            [{"name": "basic", "input": "add(1, 2)"}],
        )
        assert results[0]["type"] == "int"
        assert results[0]["value"] == "3"

    def test_str_return(self):
        results = _run_compute("javascript",
            'function greet(n) { return "Hello, " + n; }',
            [{"name": "alice", "input": 'greet("Alice")'}],
        )
        assert results[0]["type"] == "str"


class TestCCompute:
    def test_int_return(self):
        results = _run_compute("c",
            "int add(int a, int b) { return a + b; }",
            [{"name": "basic", "input": "add(1, 2)"}],
        )
        assert results[0]["type"] == "int"
        assert results[0]["value"] == "3"

    def test_float_return(self):
        results = _run_compute("c",
            "double half(double x) { return x / 2.0; }",
            [{"name": "half", "input": "half(5.0)"}],
        )
        assert results[0]["type"] == "float"
        assert "2.5" in results[0]["value"]


class TestCppCompute:
    def test_int_return(self):
        results = _run_compute("cpp",
            "int add(int a, int b) { return a + b; }",
            [{"name": "basic", "input": "add(1, 2)"}],
        )
        assert results[0]["type"] == "int"
        assert results[0]["value"] == "3"

    def test_str_return(self):
        results = _run_compute("cpp",
            '#include <string>\nstd::string greet(std::string n) { return "Hello, " + n; }',
            [{"name": "alice", "input": 'greet("Alice")'}],
        )
        assert results[0]["type"] == "str"


class TestBashCompute:
    def test_basic(self):
        results = _run_compute("bash",
            "add() { echo $(( $1 + $2 )); }",
            [{"name": "basic", "input": "add 1 2"}],
        )
        assert results[0]["type"] == "str"
        assert results[0]["value"] == "3"
