BASH_HARNESS = r"""
__results='['
_first_test=1

__escaped() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

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
        __results+='{"name":"'"$(__escaped "$name")"'","passed":true}'
    else
        __results+='{"name":"'"$(__escaped "$name")"'","passed":false,"error":"Got: '"$(__escaped "$actual")"'"}'
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
