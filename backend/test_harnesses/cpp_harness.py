CPP_HARNESS = """\
#include <iostream>
#include <string>
#include <sstream>
#include <cstring>
#include <cmath>
#include <vector>
#include <algorithm>

#define __TEST__(name, expr) do { \\
    if (!_first_test) _json_out << ","; \\
    if (expr) _json_out << "{\\"name\\":\\"" << name << "\\",\\"passed\\":true}"; \\
    else _json_out << "{\\"name\\":\\"" << name << "\\",\\"passed\\":false,\\"error\\":\\"assertion failed\\"}"; \\
    _first_test = 0; \\
} while(0)

__USER_CODE__

int main() {
    int _first_test = 1;
    std::ostringstream _json_out;
    _json_out << "{\\"results\\":[";
__TEST_CASES__
    _json_out << "]}";
    std::cout << _json_out.str();
    return 0;
}
"""


def build_cpp_script(user_code: str, test_cases: str) -> str:
    """Build a complete C++ test script from user code and test cases."""
    if user_code is None:
        raise TypeError("user_code must not be None")
    if test_cases is None:
        raise TypeError("test_cases must not be None")
    if not test_cases.strip():
        raise ValueError("test_cases must not be empty")
    # Strip user-provided main() to prevent duplicate-main compilation errors
    from . import strip_function_body
    user_code = strip_function_body(user_code, 'main')
    return CPP_HARNESS.replace("__USER_CODE__", user_code).replace("__TEST_CASES__", test_cases)
