"""Compute scripts: run solution against test_inputs to capture expected values.

Each builder returns a script that, when executed, prints:
    __RESULTS__[{"name":..., "value":..., "type":...}, ...]

Where type is one of: "str", "int", "float", "bool".
"""
from __future__ import annotations


def build_python_compute(solution: str, test_inputs: list[dict]) -> str:
    input_lines = []
    for ti in test_inputs:
        name = _escape_json(ti["name"])
        expr = ti["input"]
        input_lines.append(
            f'_results.append({{"name": "{name}", '
            f'"value": repr({expr}), '
            f'"type": __type__({expr})}})'
        )
    return _PYTHON_COMPUTE.format(
        solution=solution, test_inputs="\n".join(input_lines),
    )


def build_javascript_compute(solution: str, test_inputs: list[dict]) -> str:
    input_lines = []
    for ti in test_inputs:
        name = _escape_json(ti["name"])
        expr = ti["input"]
        input_lines.append(
            f'  results.push({{name: "{name}", value: String(__val__({expr})), type: String(__type__({expr}))}});'
        )
    return _JS_COMPUTE.format(solution=solution, test_inputs="\n".join(input_lines))


def build_c_compute(solution: str, test_inputs: list[dict]) -> str:
    printf_lines = []
    for i, ti in enumerate(test_inputs):
        name = _escape_json(ti["name"])
        expr = ti["input"]
        func_name = _extract_func_name(expr)
        ret_type = _extract_c_return_type(solution, func_name)
        fmt, ttag = _c_format_info(ret_type)
        comma = "" if i == 0 else '    printf(",");'
        if comma:
            printf_lines.append(comma)
        printf_lines.append(
            f'    printf("{{\\"name\\":\\"{name}\\",\\"value\\":\\"{fmt}\\",\\"type\\":\\"{ttag}\\"}}", {expr});'
        )
    return _C_COMPUTE.format(solution=solution, test_inputs="\n".join(printf_lines))


def build_cpp_compute(solution: str, test_inputs: list[dict]) -> str:
    cout_lines = []
    for i, ti in enumerate(test_inputs):
        name = _escape_json(ti["name"])
        expr = ti["input"]
        func_name = _extract_func_name(expr)
        ret_type = _extract_c_return_type(solution, func_name)
        _, ttag = _c_format_info(ret_type)
        comma = "" if i == 0 else '    std::cout << ",";'
        if comma:
            cout_lines.append(comma)
        cout_lines.append(
            f'    std::cout << "{{\\"name\\":\\"{name}\\",\\"value\\":\\"" << {expr} << "\\",\\"type\\":\\"{ttag}\\"}}";'
        )
    return _CPP_COMPUTE.format(solution=solution, test_inputs="\n".join(cout_lines))


def build_bash_compute(solution: str, test_inputs: list[dict]) -> str:
    result_lines = []
    for ti in test_inputs:
        name = _escape_json(ti["name"])
        expr = ti["input"]
        result_lines.append(
            f'_result=$({expr})\n'
            f'_results+=\'{{"name":"{name}","value":"\'$_result\'","type":"str"}},\''
        )
    return _BASH_COMPUTE.format(solution=solution, test_inputs="\n".join(result_lines))


# ── Template strings ──────────────────────────────────────────────────────

_PYTHON_COMPUTE = """\
{solution}

import json

def __type__(v):
    if isinstance(v, str):  return "str"
    if isinstance(v, bool): return "bool"
    if isinstance(v, float): return "float"
    if isinstance(v, int):  return "int"
    return "str"

_results = []
{test_inputs}
print("__RESULTS__" + json.dumps(_results, ensure_ascii=False))
"""

_JS_COMPUTE = """\
{solution}

function __val__(v) {{
  return (v === null || v === undefined) ? 'null' : String(v);
}}

function __type__(v) {{
  const t = typeof v;
  if (t === 'string')  return 'str';
  if (t === 'boolean') return 'bool';
  if (t === 'number')  return Number.isInteger(v) ? 'int' : 'float';
  return 'str';
}}

const results = [];
{test_inputs}
console.log("__RESULTS__" + JSON.stringify(results));
"""

_C_COMPUTE = """\
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stdbool.h>

{solution}

int main() {{
    printf("__RESULTS__[");
{test_inputs}
    printf("]");
    return 0;
}}
"""

_CPP_COMPUTE = """\
#include <iostream>
#include <string>
#include <vector>
#include <cmath>

{solution}

int main() {{
    std::cout << "__RESULTS__[";
{test_inputs}
    std::cout << "]";
    return 0;
}}
"""

_BASH_COMPUTE = """\
{solution}

_results='['
{test_inputs}
_results=${{_results%,}}
_results+=']'
echo "__RESULTS__$_results"
"""

# ── Helpers ────────────────────────────────────────────────────────────────

def _escape_json(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _extract_func_name(expr: str) -> str:
    import re
    m = re.match(r'(\w+)\(', expr)
    if m:
        return m.group(1)
    return ""


def _extract_c_return_type(solution: str, func_name: str) -> str:
    import re
    if not func_name:
        return "int"
    pattern = re.compile(
        r'([\w\s*:&<>]+?)\s+' + re.escape(func_name) + r'\s*\([^)]*\)',
        re.MULTILINE,
    )
    m = pattern.search(solution)
    if m:
        return m.group(1).strip()
    return "int"


def _c_format_info(return_type: str) -> tuple[str, str]:
    rt = return_type.strip()
    if '*' in rt:
        if 'char' in rt:
            return '%s', 'str'
        return '%p', 'int'
    if 'float' in rt or 'double' in rt:
        return '%f', 'float'
    if 'char' in rt:
        return '%c', 'str'
    if 'string' in rt:
        return '%s', 'str'
    if 'bool' in rt.lower():
        return '%d', 'bool'
    return '%d', 'int'


BUILDERS = {
    "python": build_python_compute,
    "javascript": build_javascript_compute,
    "typescript": build_javascript_compute,
    "c": build_c_compute,
    "cpp": build_cpp_compute,
    "bash": build_bash_compute,
}
