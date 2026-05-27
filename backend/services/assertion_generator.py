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
    return f'__test__("{escaped}", lambda: __assert__({tc.input} == {tc.expected}))'


def _js_assert(tc: TestCase) -> str:
    escaped = _escape_name(tc.name)
    return f'__test__("{escaped}", () => {{ __assert__(__deepEq__({tc.input}, {tc.expected})) }})'


def _c_assert(tc: TestCase) -> str:
    escaped = _escape_name(tc.name)
    if tc.type == "str":
        return f'__TEST__("{escaped}", (strcmp({tc.input}, {tc.expected}) == 0));'
    if tc.type == "float":
        return f'__APPROX__("{escaped}", {tc.input}, {tc.expected});'
    return f'__TEST__("{escaped}", ({tc.input} == {tc.expected}));'


def _cpp_assert(tc: TestCase) -> str:
    escaped = _escape_name(tc.name)
    if tc.type == "float":
        return f'__APPROX__("{escaped}", {tc.input}, {tc.expected});'
    return f'__TEST__("{escaped}", ({tc.input} == {tc.expected}));'


def _bash_assert(tc: TestCase) -> str:
    return f'__test__ "{tc.name}" "{tc.expected}" {tc.input}'
