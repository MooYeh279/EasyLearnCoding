PYTHON_HARNESS = """\
import json

__results__ = []
def __test__(name, fn):
    try:
        fn()
        __results__.append({"name": name, "passed": True})
    except Exception as e:
        __results__.append({"name": name, "passed": False,
                           "error": str(e).split("\\n")[0]})

__USER_CODE__

__TEST_CASES__

print("__RESULTS__" + json.dumps({"results": __results__}, ensure_ascii=False))
"""


def build_python_script(user_code: str, test_cases: str) -> str:
    """Build a complete Python test script from user code and test cases.

    Args:
        user_code: The user's solution code to be tested.
        test_cases: Assertion blocks using the __test__ helper.

    Returns:
        A complete Python script string ready for execution.

    Raises:
        TypeError: If either argument is None.
    """
    if user_code is None:
        raise TypeError("user_code must not be None")
    if test_cases is None:
        raise TypeError("test_cases must not be None")
    if not test_cases.strip():
        raise ValueError("test_cases must not be empty")
    return PYTHON_HARNESS.replace("__USER_CODE__", user_code).replace("__TEST_CASES__", test_cases)
