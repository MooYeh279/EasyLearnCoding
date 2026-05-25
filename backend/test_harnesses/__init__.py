from collections.abc import Callable
import re

from .bash_harness import BASH_HARNESS, build_bash_script
from .c_harness import C_HARNESS, build_c_script
from .cpp_harness import CPP_HARNESS, build_cpp_script
from .javascript_harness import JAVASCRIPT_HARNESS, build_javascript_script
from .python_harness import PYTHON_HARNESS, build_python_script


def strip_function_body(code: str, name: str) -> str:
    """Remove the body of function *name* from *code*, keeping everything else.
    Strips the return type, signature, and body (e.g. ``int main() { ... }``).
    """
    pattern = re.compile(r'[a-zA-Z_]\w*\s+' + re.escape(name) + r'\s*\([^)]*\)\s*\{')
    m = pattern.search(code)
    if not m:
        return code
    # start = beginning of return type, body_start = position of '{'
    start = m.start()
    body_start = m.end() - 1
    depth = 0
    i = body_start
    while i < len(code):
        ch = code[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return code[:start] + code[i + 1:]
        i += 1
    return code  # unbalanced braces — leave unchanged

HARNESSES: dict[str, str] = {
    "python": PYTHON_HARNESS,
    "javascript": JAVASCRIPT_HARNESS,
    "typescript": JAVASCRIPT_HARNESS,  # TS uses JS harness via tsx
    "c": C_HARNESS,
    "cpp": CPP_HARNESS,
    "bash": BASH_HARNESS,
}

BUILDERS: dict[str, Callable[[str, str], str]] = {
    "python": build_python_script,
    "javascript": build_javascript_script,
    "typescript": build_javascript_script,
    "c": build_c_script,
    "cpp": build_cpp_script,
    "bash": build_bash_script,
}
