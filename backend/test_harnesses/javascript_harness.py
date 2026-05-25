JAVASCRIPT_HARNESS = """\
const __results__ = [];
function __deepEq__(a, b) {
    if (a === b) return true;
    if (typeof a !== typeof b) return false;
    if (typeof a !== 'object' || a === null || b === null) return false;
    const ak = Object.keys(a), bk = Object.keys(b);
    if (ak.length !== bk.length) return false;
    for (const k of ak) { if (!__deepEq__(a[k], b[k])) return false; }
    return true;
}
function __assert__(cond, msg) {
    if (!cond) throw new Error(msg || "assertion failed");
}
function __test__(name, fn) {
    try { fn(); __results__.push({name, passed: true}); }
    catch(e) { __results__.push({name, passed: false, error: (e?.message ?? String(e)).split('\\n')[0]}); }
}

__USER_CODE__

__TEST_CASES__

console.log("__RESULTS__" + JSON.stringify({"results": __results__}));
"""


def build_javascript_script(user_code: str, test_cases: str) -> str:
    """Build a complete JavaScript test script from user code and test cases."""
    if user_code is None:
        raise TypeError("user_code must not be None")
    if test_cases is None:
        raise TypeError("test_cases must not be None")
    if not test_cases.strip():
        raise ValueError("test_cases must not be empty")
    return JAVASCRIPT_HARNESS.replace("__USER_CODE__", user_code).replace("__TEST_CASES__", test_cases)
