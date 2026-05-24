BASH_HARNESS = """\
__results='['
_first_test=1

escaped() { printf '%s' "$1" | sed 's/\\\\/\\\\\\\\/g; s/"/\\\\"/g; s/\x0a/\\\\n/g; s/\x0d/\\\\r/g; s/\x09/\\\\t/g'; }
export -f escaped

__test__() {
    local name="$1"; shift
    local expected="$1"; shift
    local actual
    actual=$("$@")
    if [ $_first_test -eq 1 ]; then
        _first_test=0
    else
        __results+=','
    fi
    if [ "$actual" = "$expected" ]; then
        __results+='{"name":"'"$(escaped "$name")"'","passed":true}'
    else
        __results+='{"name":"'"$(escaped "$name")"'","passed":false,"error":"Got: '"$(escaped "$actual")"'"}'
    fi
}

__USER_CODE__

__TEST_CASES__

__results+=']'
echo "__RESULTS__$__results"
"""


def build_bash_script(user_code: str, test_cases: str) -> str:
    """Build a complete Bash test script from user code and test cases."""
    if user_code is None:
        raise TypeError("user_code must not be None")
    if test_cases is None:
        raise TypeError("test_cases must not be None")
    if not test_cases.strip():
        raise ValueError("test_cases must not be empty")
    return BASH_HARNESS.replace("__USER_CODE__", user_code).replace("__TEST_CASES__", test_cases)
