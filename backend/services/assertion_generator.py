"""Generate harness-ready assertion code from TestCaseSpec per language."""
from __future__ import annotations

from services.exercise_schema import TestCaseSpec


def generate_assertions(language: str, test_cases: list[TestCaseSpec]) -> str:
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


def _is_float_value(expr: str) -> bool:
    """Check if an expression contains a floating-point literal (has a decimal point)."""
    import re
    return bool(re.search(r'\d\.\d', expr))


def _python_assert(tc: TestCaseSpec) -> str:
    escaped = _escape_name(tc.name)
    return f'__test__("{escaped}", lambda: __assert__({tc.input} == {tc.expected}))'


def _js_assert(tc: TestCaseSpec) -> str:
    escaped = _escape_name(tc.name)
    # Use __deepEq__ instead of === because === is reference equality for arrays/objects.
    return f'__test__("{escaped}", () => {{ __assert__(__deepEq__({tc.input}, {tc.expected})) }})'


def _c_assert(tc: TestCaseSpec) -> str:
    escaped = _escape_name(tc.name)
    if tc.is_string:
        return f'__TEST__("{escaped}", (strcmp({tc.input}, {tc.expected}) == 0));'
    if _is_float_value(tc.input) or _is_float_value(tc.expected):
        return f'__APPROX__("{escaped}", {tc.input}, {tc.expected});'
    return f'__TEST__("{escaped}", ({tc.input} == {tc.expected}));'


def _cpp_assert(tc: TestCaseSpec) -> str:
    escaped = _escape_name(tc.name)
    if _is_float_value(tc.input) or _is_float_value(tc.expected):
        return f'__APPROX__("{escaped}", {tc.input}, {tc.expected});'
    return f'__TEST__("{escaped}", ({tc.input} == {tc.expected}));'


def _bash_assert(tc: TestCaseSpec) -> str:
    return f'__test__ "{tc.name}" "{tc.expected}" {tc.input}'
