CPP_HARNESS = """\
#include <iostream>
#include <string>

#define __TEST__(name, expr) do { \\
    if (!_first_test) std::cout << ","; \\
    if (expr) std::cout << "{\\"name\\":\\"" << name << "\\",\\"passed\\":true}"; \\
    else std::cout << "{\\"name\\":\\"" << name << "\\",\\"passed\\":false,\\"error\\":\\"assertion failed\\"}"; \\
    _first_test = 0; \\
} while(0)

__USER_CODE__

int main() {
    int _first_test = 1;
    std::cout << "{\\"results\\":[";
__TEST_CASES__
    std::cout << "]}";
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
    return CPP_HARNESS.replace("__USER_CODE__", user_code).replace("__TEST_CASES__", test_cases)
