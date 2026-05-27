"""Generate harness-ready assertion code from TestCase per language."""
from __future__ import annotations

from services.exercise_schema import TestCase


def generate_assertions(language: str, test_cases: list[TestCase]) -> str:
    """Return harness-ready assertion code for all test cases."""
    dispatchers = {
        "python": _python_assert,
        "javascript": _js_assert,
        "typescript": _js_assert,
        "c": _c_assert,
        "cpp": _cpp_assert,
        "bash": _bash_assert,
    }
    fn = dispatchers.get(language)
    if not fn:
        return ""
    return "\n".join(fn(tc) for tc in test_cases)


def _escape_name(name: str) -> str:
    """Escape double-quotes in test case names for string literals."""
    return name.replace("\\", "\\\\").replace('"', '\\"')


def _python_assert(tc: TestCase) -> str:
    escaped = _escape_name(tc.name)
    return f'__test__("{escaped}", lambda: __check__({tc.input}, {tc.expected}))'


def _js_assert(tc: TestCase) -> str:
    escaped = _escape_name(tc.name)
    expected = tc.expected
    if tc.type == "str":
        expected_escaped = expected.replace("\\", "\\\\").replace('"', '\\"')
        expected = f'"{expected_escaped}"'
    return f'__test__("{escaped}", () => {{ __check__({tc.input}, {expected}) }})'


def _c_assert(tc: TestCase) -> str:
    escaped = _escape_name(tc.name)
    expected_str = tc.expected.replace("\\", "\\\\").replace('"', '\\"')
    if tc.type == "str":
        return f'__TEST__("{escaped}", (strcmp({tc.input}, "{expected_str}") == 0), "{expected_str}");'
    if tc.type == "char":
        return f'__TEST__("{escaped}", ({tc.input} == \'{expected_str}\'), "\'{expected_str}\'");'
    if tc.type == "float":
        return f'__APPROX__("{escaped}", {tc.input}, {tc.expected});'
    return f'__TEST__("{escaped}", ({tc.input} == {tc.expected}), "{expected_str}");'


def _cpp_assert(tc: TestCase) -> str:
    escaped = _escape_name(tc.name)
    expected_str = tc.expected.replace("\\", "\\\\").replace('"', '\\"')
    if tc.type == "str":
        return f'__TEST__("{escaped}", ({tc.input} == "{expected_str}"), "\\"{expected_str}\\"");'
    if tc.type == "char":
        return f'__TEST__("{escaped}", ({tc.input} == \'{expected_str}\'), "\'{expected_str}\'");'
    if tc.type == "float":
        return f'__APPROX__("{escaped}", {tc.input}, {tc.expected});'
    return f'__TEST__("{escaped}", ({tc.input} == {tc.expected}), "{expected_str}");'


def _bash_assert(tc: TestCase) -> str:
    return f'__test__ "{tc.name}" "{tc.expected}" {tc.input}'
