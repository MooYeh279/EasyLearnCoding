C_HARNESS = """\
#include <stdio.h>
#include <stdlib.h>

#define __TEST__(name, expr) do { \\
    if (!_first_test) printf(","); \\
    if (expr) printf("{\\"name\\":\\"%s\\",\\"passed\\":true}", name); \\
    else printf("{\\"name\\":\\"%s\\",\\"passed\\":false,\\"error\\":\\"assertion failed\\"}", name); \\
    _first_test = 0; \\
} while(0)

__USER_CODE__

int main() {
    int _first_test = 1;
    printf("{\\"results\\":[");
__TEST_CASES__
    printf("]}");
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
    return C_HARNESS.replace("__USER_CODE__", user_code).replace("__TEST_CASES__", test_cases)
