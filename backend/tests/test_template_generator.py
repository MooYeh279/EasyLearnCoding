"""Tests for template_generator — deterministic template from FunctionSignature."""
from services.exercise_schema import FunctionSignature


def test_python_template():
    from services.template_generator import generate_template

    sigs = [FunctionSignature(name="add", params="a, b", return_type="")]
    result = generate_template("python", sigs)
    assert "def add(a, b):" in result
    assert "# TODO: implement" in result
    assert "pass" in result


def test_javascript_template():
    from services.template_generator import generate_template

    sigs = [FunctionSignature(name="add", params="a, b", return_type="")]
    result = generate_template("javascript", sigs)
    assert "function add(a, b) {" in result
    assert "// TODO: implement" in result


def test_typescript_template():
    from services.template_generator import generate_template

    sigs = [FunctionSignature(name="add", params="a: number, b: number", return_type=": number")]
    result = generate_template("typescript", sigs)
    assert "function add(a: number, b: number): number {" in result
    assert "// TODO: implement" in result


def test_c_template():
    from services.template_generator import generate_template

    sigs = [FunctionSignature(name="add", params="int a, int b", return_type="int")]
    result = generate_template("c", sigs)
    assert "int add(int a, int b) {" in result
    assert "/* TODO: implement */" in result
    assert "return 0;" in result


def test_cpp_template():
    from services.template_generator import generate_template

    sigs = [FunctionSignature(name="add", params="int a, int b", return_type="int")]
    result = generate_template("cpp", sigs)
    assert "int add(int a, int b) {" in result
    assert "// TODO: implement" in result
    assert "return 0;" in result


def test_bash_template():
    from services.template_generator import generate_template

    sigs = [FunctionSignature(name="add", params="", return_type="")]
    result = generate_template("bash", sigs)
    assert "add() {" in result
    assert "# TODO: implement" in result


def test_multiple_functions():
    from services.template_generator import generate_template

    sigs = [
        FunctionSignature(name="add", params="a, b", return_type=""),
        FunctionSignature(name="sub", params="a, b", return_type=""),
    ]
    result = generate_template("python", sigs)
    assert "def add(a, b):" in result
    assert "def sub(a, b):" in result


def test_unsupported_language_returns_empty():
    from services.template_generator import generate_template

    sigs = [FunctionSignature(name="f", params="", return_type="")]
    result = generate_template("rust", sigs)
    assert result == ""


def test_verify_signatures_in_solution():
    from services.template_generator import verify_signatures_in_solution
    from services.exercise_schema import FunctionSignature

    sigs = [FunctionSignature(name="add", params="a, b", return_type="")]
    assert verify_signatures_in_solution(sigs, "def add(a, b):\n    return a + b") is True
    assert verify_signatures_in_solution(sigs, "def multiply(a, b):\n    return a * b") is False


def test_c_void_function():
    from services.template_generator import generate_template

    sigs = [FunctionSignature(name="print_msg", params="const char *msg", return_type="void")]
    result = generate_template("c", sigs)
    assert "void print_msg(const char *msg) {" in result
    assert "return 0;" not in result
