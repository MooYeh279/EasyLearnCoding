from collections.abc import Callable

from .bash_harness import BASH_HARNESS, build_bash_script
from .c_harness import C_HARNESS, build_c_script
from .cpp_harness import CPP_HARNESS, build_cpp_script
from .javascript_harness import JAVASCRIPT_HARNESS, build_javascript_script
from .python_harness import PYTHON_HARNESS, build_python_script

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
