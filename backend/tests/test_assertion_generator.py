"""Tests for assertion_generator with new TestCase model (type field)."""
from services.exercise_schema import TestCase


def test_python_basic():
    from services.assertion_generator import generate_assertions
    cases = [TestCase(name="basic", input="add(1, 2)", expected="3", type="int")]
    result = generate_assertions("python", cases)
    assert '__test__("basic", lambda: __check__(add(1, 2), 3))' in result


def test_python_string():
    from services.assertion_generator import generate_assertions
    cases = [TestCase(name="greet", input="greet()", expected="'hello'", type="str")]
    result = generate_assertions("python", cases)
    assert "__check__(greet(), 'hello')" in result


def test_js_basic():
    from services.assertion_generator import generate_assertions
    cases = [TestCase(name="basic", input="add(1, 2)", expected="3", type="int")]
    result = generate_assertions("javascript", cases)
    assert "__check__" in result
    assert "add(1, 2), 3)" in result  # number no quotes


def test_js_string_quoted():
    from services.assertion_generator import generate_assertions
    cases = [TestCase(name="greet", input='greet("Alice")', expected="Hello, Alice", type="str")]
    result = generate_assertions("javascript", cases)
    assert '"Hello, Alice"' in result  # string wrapped in quotes


def test_c_int():
    from services.assertion_generator import generate_assertions
    cases = [TestCase(name="basic", input="add(1, 2)", expected="3", type="int")]
    result = generate_assertions("c", cases)
    assert '__TEST__("basic", (add(1, 2) == 3), "3");' in result
    assert "strcmp" not in result


def test_c_string_uses_strcmp():
    from services.assertion_generator import generate_assertions
    cases = [TestCase(name="greet", input='greet()', expected="hello", type="str")]
    result = generate_assertions("c", cases)
    assert "strcmp" in result
    assert '"hello"' in result


def test_c_float_uses_approx():
    from services.assertion_generator import generate_assertions
    cases = [TestCase(name="pi", input="getPi()", expected="3.14", type="float")]
    result = generate_assertions("c", cases)
    assert "__APPROX__" in result


def test_cpp_string_uses_equality():
    from services.assertion_generator import generate_assertions
    cases = [TestCase(name="greet", input='greet("Alice")', expected="Hello", type="str")]
    result = generate_assertions("cpp", cases)
    assert "strcmp" not in result
    assert "==" in result
    assert '"Hello"' in result


def test_cpp_float_uses_approx():
    from services.assertion_generator import generate_assertions
    cases = [TestCase(name="pi", input="getPi()", expected="3.14", type="float")]
    result = generate_assertions("cpp", cases)
    assert "__APPROX__" in result


def test_bash_basic():
    from services.assertion_generator import generate_assertions
    cases = [TestCase(name="basic", input="add 1 2", expected="3", type="int")]
    result = generate_assertions("bash", cases)
    assert '__test__ "basic" "3" add 1 2' in result


def test_unsupported_language_returns_empty():
    from services.assertion_generator import generate_assertions
    cases = [TestCase(name="basic", input="f()", expected="1", type="int")]
    result = generate_assertions("rust", cases)
    assert result == ""


def test_name_with_quotes_escaped():
    from services.assertion_generator import generate_assertions
    cases = [TestCase(name='test "alpha"', input="f()", expected="1", type="int")]
    result = generate_assertions("python", cases)
    assert '__test__("test \\"alpha\\"", lambda: __check__(f(), 1))' in result
