C_HARNESS = """\
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define _JSON_BUF_SIZE 8192

#define __TEST__(name, expr) do { \\
    if (!_first_test) strncat(_json_buf, ",", _JSON_BUF_SIZE - strlen(_json_buf) - 1); \\
    { char _entry[512]; \\
      snprintf(_entry, sizeof(_entry), \\
        (expr) \\
            ? "{\\"name\\":\\"%s\\",\\"passed\\":true}" \\
            : "{\\"name\\":\\"%s\\",\\"passed\\":false,\\"error\\":\\"assertion failed\\"}", \\
        name); \\
      strncat(_json_buf, _entry, _JSON_BUF_SIZE - strlen(_json_buf) - 1); } \\
    _first_test = 0; \\
} while(0)

__USER_CODE__

int main() {
    int _first_test = 1;
    char _json_buf[_JSON_BUF_SIZE] = {0};
    strncpy(_json_buf, "{\\"results\\":[", _JSON_BUF_SIZE - 1);
__TEST_CASES__
    strncat(_json_buf, "]}", _JSON_BUF_SIZE - strlen(_json_buf) - 1);
    printf("%s", _json_buf);
    return 0;
}
"""


def build_c_script(user_code: str, test_cases: str) -> str:
    """Build a complete C test script from user code and test cases."""
    if user_code is None:
        raise TypeError("user_code must not be None")
    if test_cases is None:
        raise TypeError("test_cases must not be None")
    if not test_cases.strip():
        raise ValueError("test_cases must not be empty")
    # Strip user-provided main() to prevent duplicate-main compilation errors
    import re
    user_code = re.sub(
        r'\bint\s+main\s*\([^)]*\)\s*\{.*', '', user_code, flags=re.DOTALL
    )
    return C_HARNESS.replace("__USER_CODE__", user_code).replace("__TEST_CASES__", test_cases)
