"""Generate deterministic starter templates from FunctionSignature per language."""
from __future__ import annotations

from services.exercise_schema import FunctionSignature


def generate_template(language: str, signatures: list[FunctionSignature]) -> str:
    """Return starter code template from function signatures."""
    dispatchers = {
        "python": _python_template,
        "javascript": _js_template,
        "typescript": _ts_template,
        "c": _c_template,
        "cpp": _cpp_template,
        "bash": _bash_template,
    }
    fn = dispatchers.get(language)
    if not fn:
        return ""
    parts: list[str] = []
    for sig in signatures:
        parts.append(fn(sig))
    return "\n\n".join(parts)


def verify_signatures_in_solution(
    signatures: list[FunctionSignature], solution: str
) -> bool:
    """Check that every signature name appears in the solution code."""
    return all(sig.name in solution for sig in signatures)


def _python_template(sig: FunctionSignature) -> str:
    return f"def {sig.name}({sig.params}):\n    # TODO: implement\n    pass"


def _js_template(sig: FunctionSignature) -> str:
    return f"function {sig.name}({sig.params}) {{\n  // TODO: implement\n}}"


def _ts_template(sig: FunctionSignature) -> str:
    return f"function {sig.name}({sig.params}){sig.return_type} {{\n  // TODO: implement\n}}"


def _c_template(sig: FunctionSignature) -> str:
    if sig.return_type == "void":
        return f"{sig.return_type} {sig.name}({sig.params}) {{\n    /* TODO: implement */\n}}"
    return f"{sig.return_type} {sig.name}({sig.params}) {{\n    /* TODO: implement */\n    return 0;\n}}"


def _cpp_template(sig: FunctionSignature) -> str:
    if sig.return_type == "void":
        return f"{sig.return_type} {sig.name}({sig.params}) {{\n    // TODO: implement\n}}"
    return f"{sig.return_type} {sig.name}({sig.params}) {{\n    // TODO: implement\n    return 0;\n}}"


def _bash_template(sig: FunctionSignature) -> str:
    return f"{sig.name}() {{\n  # TODO: implement\n}}"
