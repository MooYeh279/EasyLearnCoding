"""Generate exercise templates from solution code by stripping implementation bodies.

The template is the solution with every function/method/constructor body replaced
by a TODO placeholder.  This works for standalone functions AND class-based
exercises across all supported languages.
"""
from __future__ import annotations

import re

from services.exercise_schema import FunctionSignature


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_template_from_solution(solution: str, language: str) -> str:
    """Return a starter template derived from *solution* by replacing every
    function / method / constructor body with a TODO placeholder.

    Falls back to returning the solution unchanged for unsupported languages.
    """
    dispatchers = {
        "python": _strip_python,
        "javascript": _strip_brace_lang,
        "typescript": _strip_brace_lang,
        "c": _strip_brace_lang,
        "cpp": _strip_brace_lang,
        "bash": _strip_bash,
    }
    fn = dispatchers.get(language)
    if not fn:
        return solution
    template = fn(solution)
    # Remove main() and any entry-point guard from the template —
    # the test harness provides its own entry point.
    from test_harnesses import strip_function_body
    template = strip_function_body(template, 'main')
    # Python: strip `if __name__ == "__main__":` block
    if language == "python":
        template = _strip_main_guard(template)
    return template


def _strip_main_guard(code: str) -> str:
    """Remove ``if __name__ == \"__main__\":`` block from Python code."""
    import re
    pattern = re.compile(r'if\s+__name__\s*==\s*["\']__main__["\']\s*:')
    m = pattern.search(code)
    if not m:
        return code
    start = m.start()
    # Find the indented block that follows
    lines = code[start:].splitlines()
    if not lines:
        return code
    # Find base indentation of the `if` line
    base_indent = len(lines[0]) - len(lines[0].lstrip())
    # Collect lines belonging to this block (indented more than base)
    block_lines = [lines[0]]
    for line in lines[1:]:
        stripped = line.lstrip()
        if not stripped:  # empty line within block
            block_lines.append(line)
            continue
        indent = len(line) - len(stripped)
        if indent <= base_indent:
            break
        block_lines.append(line)
    # Remove block plus leading blank line before it, if any
    before = code[:start].rstrip('\n')
    after_start = start
    for bl in block_lines:
        after_start = code.find(bl, after_start) + len(bl)
    after = code[after_start:]
    # Remove trailing newline after the block
    after = after.lstrip('\n')
    return before + '\n' + after if after else before


def verify_signatures_in_solution(
    signatures: list[FunctionSignature], solution: str
) -> bool:
    """Check that every signature name appears in the solution code."""
    return all(sig.name in solution for sig in signatures)


# ---------------------------------------------------------------------------
# Python — indentation-based body stripping
# ---------------------------------------------------------------------------

def _strip_python(solution: str) -> str:
    lines = solution.splitlines()
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Blank line: keep
        if stripped == "":
            result.append(line)
            i += 1
            continue

        # def or class block header
        if stripped.startswith(("def ", "class ")) and line.rstrip().endswith(":"):
            result.append(line)
            # For class: process inner members instead of skipping the whole body
            if stripped.startswith("class "):
                i = _process_python_class_body(lines, i, result, indent)
            else:
                i = _append_python_body_pass(lines, i, result, indent)
            continue

        # Decorator line — keep and check next line
        if stripped.startswith("@"):
            result.append(line)
            i += 1
            continue

        # Any other top-level or indented line (imports, assignments, etc.)
        result.append(line)
        i += 1

    return "\n".join(result)


def _process_python_class_body(
    lines: list[str], class_idx: int, result: list[str], class_indent: int,
) -> int:
    """Process the body of a Python class: keep field assignments, method
    signatures, decorators; strip method bodies with ``pass``.
    """
    body_indent = class_indent + 4
    i = class_idx + 1

    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Blank line: keep
        if stripped == "":
            result.append(line)
            i += 1
            continue

        # Dedented past the class body: class is done
        if indent < body_indent:
            break

        # Decorator: keep, advance
        if stripped.startswith("@"):
            result.append(line)
            i += 1
            continue

        # Method header (def inside the class)
        if stripped.startswith("def ") and line.rstrip().endswith(":"):
            result.append(line)
            i = _append_python_body_pass(lines, i, result, indent)
            continue

        # Class-level assignment or type annotation: keep
        # (e.g. `count = 0`, `name: str`, `_items: list = []`)
        result.append(line)
        i += 1

    return i


def _append_python_body_pass(
    lines: list[str], sig_idx: int, result: list[str], sig_indent: int,
) -> int:
    """Advance past the body of a ``def`` block starting at *sig_idx*,
    appending a ``pass`` placeholder to *result*.  Returns the next line index.
    """
    body_indent = sig_indent + 4
    result.append(" " * body_indent + "pass")
    i = sig_idx + 1
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if stripped == "":
            i += 1
            continue
        if indent >= body_indent:
            i += 1
            continue
        break
    return i


# ---------------------------------------------------------------------------
# C / C++ / JS / TS — brace-based body stripping
# ---------------------------------------------------------------------------

# Regex to identify a function/method/constructor header in brace-based languages.
# Matches patterns like:
#   int add(int a, int b) {
#   function add(a, b) {
#   constructor(brand: string) {
#   std::string getBrand() {
#   static int getCount() {
#   void process() const {
#   getBrand(): string {
#   static getVehicleCount(): number {
# Does NOT match control flow: if (...), for (...), while (...), switch (...), catch (...)
_FUNC_HEADER_RE = re.compile(
    r"^(?!"          # negative lookahead — reject control flow
    r"if\s*\(|for\s*\(|while\s*\(|switch\s*\(|catch\s*\(|else"
    r")"
    r".*?"           # optional prefix (return type, static, etc.)
    r"\w+\s*"        # function name
    r"\(.*?\)"       # parameter list
    r".*?"           # optional suffix (const, : return_type, etc.)
    r"\{\s*$"        # opening brace at end of line
)

# Regex to identify a class/struct/interface header
_CONTAINER_HEADER_RE = re.compile(
    r"(?:^|\s)"
    r"(class|struct|interface)\s+\w+"
    r".*?"
    r"\{\s*$"
)


def _strip_brace_lang(solution: str) -> str:
    lines = solution.splitlines()
    result: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Blank / comment / preprocessor / using / import: keep as-is
        if _is_verbatim_line(stripped):
            result.append(line)
            i += 1
            continue

        # Class / struct / interface header
        if _CONTAINER_HEADER_RE.search(stripped):
            result.append(line)
            i = _process_brace_container(lines, i, result)
            continue

        # Function / method / constructor header
        if _FUNC_HEADER_RE.search(stripped):
            result.append(line)
            i = _strip_brace_body(lines, i, result, stripped)
            continue

        # Function header with brace on the next line:
        #   int add(int a, int b)     <- current line (has parens, no brace)
        #   {                         <- next line
        if "(" in stripped and ")" in stripped and "{" not in stripped:
            if i + 1 < len(lines) and lines[i + 1].strip() == "{":
                if not _is_control_flow(stripped):
                    result.append(line)
                    result.append(lines[i + 1])  # the `{`
                    i = _strip_brace_body_after_open(lines, i + 1, result, stripped)
                    continue

        # Enum declaration (single line or multi-line): keep verbatim
        if stripped.startswith("enum "):
            i = _keep_verbatim_block(lines, i, result)
            continue

        # Any other line: keep
        result.append(line)
        i += 1

    return "\n".join(result)


def _is_verbatim_line(stripped: str) -> bool:
    """Lines that should be kept verbatim without body-stripping logic."""
    if stripped == "":
        return True
    if stripped.startswith("#"):
        return True
    if stripped.startswith("using "):
        return True
    if stripped.startswith(("import ", "export ")):
        return True
    if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
        return True
    if stripped in ("public:", "private:", "protected:"):
        return True
    return False


def _is_control_flow(stripped: str) -> bool:
    """Return True if *stripped* is a control-flow keyword, not a function."""
    for kw in ("if ", "if(", "for ", "for(", "while ", "while(", "switch ", "switch(", "catch ", "catch("):
        if stripped.startswith(kw):
            return True
    if stripped.startswith("else"):
        return True
    return False


def _process_brace_container(
    lines: list[str], header_idx: int, result: list[str],
) -> int:
    """Process a class/struct body: keep field declarations, strip method bodies."""
    i = header_idx + 1
    brace_depth = lines[header_idx].count("{") - lines[header_idx].count("}")

    if brace_depth == 0:
        # Opening brace on the next line
        if i < len(lines) and lines[i].strip() == "{":
            result.append(lines[i])
            brace_depth = 1
            i += 1
        else:
            return i

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        old_depth = brace_depth
        brace_depth += line.count("{") - line.count("}")

        if brace_depth <= 0:
            result.append(line)
            return i + 1

        # Inside the class body

        # Verbatim lines
        if _is_verbatim_line(stripped):
            result.append(line)
            i += 1
            continue

        # Access modifiers
        if stripped in ("public:", "private:", "protected:"):
            result.append(line)
            i += 1
            continue

        # Method / constructor inside the class
        if _FUNC_HEADER_RE.search(stripped):
            result.append(line)
            i = _strip_brace_body(lines, i, result, stripped)
            brace_depth = 0  # _strip_brace_body consumed the closing brace
            # We need to re-check brace_depth from current position
            # Actually, after _strip_brace_body returns, we should be past the method
            # and back inside the class body. Let's recalculate.
            continue

        # Method with brace on next line
        if "(" in stripped and ")" in stripped and "{" not in stripped:
            if i + 1 < len(lines) and lines[i + 1].strip() == "{":
                if not _is_control_flow(stripped):
                    result.append(line)
                    result.append(lines[i + 1])
                    i = _strip_brace_body_after_open(lines, i + 1, result, stripped)
                    continue

        # Nested container (unlikely in exercises)
        if _CONTAINER_HEADER_RE.search(stripped):
            result.append(line)
            i = _process_brace_container(lines, i, result)
            brace_depth = 0  # recalculated in next iteration
            continue

        # Field / property declaration (no opening brace on this line)
        # e.g. `int x;`, `static int count;`, `private brand: string;`,
        # `std::string name;`, `double x, y;`
        if "{" not in stripped:
            result.append(line)
            i += 1
            continue

        # Other lines inside class body
        result.append(line)
        i += 1

    return i


def _strip_brace_body(
    lines: list[str], header_idx: int, result: list[str], header_stripped: str,
) -> int:
    """Strip the body of a function/method/constructor whose header (with ``{``)
    is at *header_idx*, replacing with TODO and a default return.
    Returns the next line index after the closing brace.
    """
    ret = _default_return(header_stripped)
    placeholder_lines = ["    // TODO: implement"]
    if ret:
        placeholder_lines.append(f"    {ret}")

    i = header_idx + 1
    brace_depth = lines[header_idx].count("{") - lines[header_idx].count("}")

    if brace_depth == 0:
        return i + 1  # shouldn't happen but be safe

    # If the body starts on the same line as the header (e.g. `int f() { return 0; }`)
    if brace_depth == 0:
        return i

    result.append("\n".join(placeholder_lines))

    while i < len(lines):
        brace_depth += lines[i].count("{") - lines[i].count("}")
        if brace_depth <= 0:
            result.append("}")
            return i + 1
        i += 1

    return i


def _strip_brace_body_after_open(
    lines: list[str], open_brace_idx: int, result: list[str], header_stripped: str,
) -> int:
    """Like _strip_brace_body but the opening ``{`` is on its own line at
    *open_brace_idx* and has already been appended to *result*.
    """
    ret = _default_return(header_stripped)
    placeholder_lines = ["    // TODO: implement"]
    if ret:
        placeholder_lines.append(f"    {ret}")
    result.append("\n".join(placeholder_lines))

    i = open_brace_idx + 1
    brace_depth = 1  # we already saw the `{`

    while i < len(lines):
        brace_depth += lines[i].count("{") - lines[i].count("}")
        if brace_depth <= 0:
            result.append("}")
            return i + 1
        i += 1

    return i


def _default_return(header_stripped: str) -> str:
    """Return a default return statement for the given function header, or
    empty string for void/constructor.
    """
    lower = header_stripped.lower()

    # Constructor — no return
    if lower.startswith("constructor") or lower.startswith("constructor("):
        return ""

    # void return type
    if re.search(r"\bvoid\b", lower):
        return ""

    # Bool return type
    if re.search(r"\bbool\b", lower) or ": bool" in lower or ": boolean" in lower:
        return "return false;"

    # String return type
    if re.search(r"\bstring\b", lower) or "char*" in lower or "const char" in lower:
        return 'return "";'

    # Numeric return type
    if re.search(r"\b(int|long|double|float)\b", lower) or ": number" in lower:
        return "return 0;"

    # Generic fallback
    return "return 0;"


def _keep_verbatim_block(lines: list[str], start_idx: int, result: list[str]) -> int:
    """Keep lines verbatim until we find the closing brace of the block."""
    i = start_idx
    brace_depth = 0
    while i < len(lines):
        line = lines[i]
        result.append(line)
        brace_depth += line.count("{") - line.count("}")
        if brace_depth <= 0 and i > start_idx:
            return i + 1
        i += 1
    return i


# ---------------------------------------------------------------------------
# Bash — function body stripping
# ---------------------------------------------------------------------------

def _strip_bash(solution: str) -> str:
    lines = solution.splitlines()
    result: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Detect function definition: name() { or function name {
        if _is_bash_func_header(stripped):
            result.append(line)
            # Find the opening brace
            if "{" in line:
                result.append("  :  # TODO: implement")
                i = _skip_to_closing_brace(lines, i)
                result.append("}")
            else:
                # Opening brace on next line
                i += 1
                if i < len(lines) and lines[i].strip() == "{":
                    result.append("{")
                    result.append("  :  # TODO: implement")
                    i = _skip_to_closing_brace(lines, i)
                    result.append("}")
            continue

        result.append(line)
        i += 1

    return "\n".join(result)


def _is_bash_func_header(stripped: str) -> bool:
    """Return True if the line looks like a Bash function definition header."""
    if stripped.startswith("function "):
        return True
    # name() { pattern
    if "()" in stripped:
        before = stripped[:stripped.index("()")].strip()
        if before and (before[0].isalpha() or before[0] == "_"):
            return True
    return False


def _skip_to_closing_brace(lines: list[str], start_idx: int) -> int:
    """Return the index after the closing brace of the block opened at *start_idx*."""
    depth = 0
    i = start_idx
    while i < len(lines):
        depth += lines[i].count("{") - lines[i].count("}")
        if depth <= 0 and i > start_idx:
            return i + 1
        i += 1
    return i
