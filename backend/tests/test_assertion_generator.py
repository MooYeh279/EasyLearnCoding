"""Tests for assertion_generator — deterministic assertion code from TestCaseSpec."""
from services.exercise_schema import TestCaseSpec


def test_python_basic():
    from services.assertion_generator import generate_assertions

    cases = [
        TestCaseSpec(name="basic", input="add(1, 2)", expected="3"),
        TestCaseSpec(name="zero", input="add(0, 0)", expected="0"),
    ]
    result = generate_assertions("python", cases)
    assert '__test__("basic", lambda: __assert__(add(1, 2) == 3))' in result
    assert '__test__("zero", lambda: __assert__(add(0, 0) == 0))' in result


def test_javascript_basic():
    from services.assertion_generator import generate_assertions

    cases = [TestCaseSpec(name="basic", input="add(1, 2)", expected="3")]
    result = generate_assertions("javascript", cases)
    assert '__test__("basic", () => { __assert__(__deepEq__(add(1, 2), 3)) })' in result


def test_typescript_basic():
    from services.assertion_generator import generate_assertions

    cases = [TestCaseSpec(name="basic", input="add(1, 2)", expected="3")]
    result = generate_assertions("typescript", cases)
    assert '__test__("basic", () => { __assert__(__deepEq__(add(1, 2), 3)) })' in result


def test_c_basic():
    from services.assertion_generator import generate_assertions

    cases = [TestCaseSpec(name="basic", input="add(1, 2)", expected="3")]
    result = generate_assertions("c", cases)
    assert '__TEST__("basic", (add(1, 2) == 3));' in result


def test_cpp_basic():
    from services.assertion_generator import generate_assertions

    cases = [TestCaseSpec(name="basic", input="add(1, 2)", expected="3")]
    result = generate_assertions("cpp", cases)
    assert '__TEST__("basic", (add(1, 2) == 3));' in result


def test_c_string_comparison():
    from services.assertion_generator import generate_assertions

    cases = [TestCaseSpec(name="greet", input='greet()', expected='"hello"', is_string=True)]
    result = generate_assertions("c", cases)
    assert '__TEST__("greet", (strcmp(greet(), "hello") == 0));' in result


def test_bash_basic():
    from services.assertion_generator import generate_assertions

    cases = [TestCaseSpec(name="basic", input="add 1 2", expected="3")]
    result = generate_assertions("bash", cases)
    assert '__test__ "basic" "3" add 1 2' in result


def test_unsupported_language_returns_empty():
    from services.assertion_generator import generate_assertions

    cases = [TestCaseSpec(name="basic", input="f()", expected="1")]
    result = generate_assertions("rust", cases)
    assert result == ""


def test_name_with_quotes_escaped():
    from services.assertion_generator import generate_assertions

    cases = [TestCaseSpec(name='test "alpha"', input="f()", expected="1")]
    result = generate_assertions("python", cases)
    assert '__test__("test \\"alpha\\"", lambda: __assert__(f() == 1))' in result


def test_expected_string_literal():
    from services.assertion_generator import generate_assertions

    cases = [TestCaseSpec(name="str", input="greet()", expected='"hello"')]
    result = generate_assertions("python", cases)
    assert '__assert__(greet() == "hello")' in result


def test_expected_list_literal():
    from services.assertion_generator import generate_assertions

    cases = [TestCaseSpec(name="list", input="range3()", expected="[0, 1, 2]")]
    result = generate_assertions("python", cases)
    assert "__assert__(range3() == [0, 1, 2])" in result


def test_cpp_string_uses_equality():
    """C++ string assertions must use ==, not strcmp (std::string supports ==)."""
    from services.assertion_generator import generate_assertions

    cases = [TestCaseSpec(name="greet", input='greet("Alice")', expected='"Hello, Alice!"', is_string=True)]
    result = generate_assertions("cpp", cases)
    assert '__TEST__("greet", (greet("Alice") == "Hello, Alice!"));' in result
    assert "strcmp" not in result


def test_c_string_uses_strcmp():
    """C string assertions must use strcmp (no == for char*)."""
    from services.assertion_generator import generate_assertions

    cases = [TestCaseSpec(name="greet", input='greet()', expected='"hello"', is_string=True)]
    result = generate_assertions("c", cases)
    assert "strcmp" in result


def test_cpp_non_string_uses_equality():
    """C++ non-string assertions use == (same as before)."""
    from services.assertion_generator import generate_assertions

    cases = [TestCaseSpec(name="add", input="add(1, 2)", expected="3")]
    result = generate_assertions("cpp", cases)
    assert '__TEST__("add", (add(1, 2) == 3));' in result
