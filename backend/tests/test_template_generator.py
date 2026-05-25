"""Tests for template_generator — generate_template_from_solution."""
from services.template_generator import generate_template_from_solution


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

class TestPythonTemplate:
    def test_standalone_function(self):
        solution = "def add(a, b):\n    return a + b"
        result = generate_template_from_solution(solution, "python")
        assert "def add(a, b):" in result
        assert "pass" in result
        assert "return a + b" not in result

    def test_class_with_methods(self):
        solution = (
            "class Vehicle:\n"
            "    count = 0\n"
            "\n"
            "    def __init__(self, brand):\n"
            "        self.brand = brand\n"
            "        Vehicle.count += 1\n"
            "\n"
            "    def getBrand(self):\n"
            "        return self.brand\n"
            "\n"
            "    @staticmethod\n"
            "    def getVehicleCount():\n"
            "        return Vehicle.count\n"
        )
        result = generate_template_from_solution(solution, "python")
        assert "class Vehicle:" in result
        assert "count = 0" in result
        assert "def __init__(self, brand):" in result
        assert "def getBrand(self):" in result
        assert "def getVehicleCount():" in result
        assert "pass" in result
        # Implementation should be stripped
        assert "self.brand" not in result
        assert "Vehicle.count += 1" not in result
        assert "return self.brand" not in result

    def test_multiple_top_level_functions(self):
        solution = (
            "def add(a, b):\n"
            "    return a + b\n"
            "\n"
            "def sub(a, b):\n"
            "    return a - b\n"
        )
        result = generate_template_from_solution(solution, "python")
        assert "def add(a, b):" in result
        assert "def sub(a, b):" in result
        assert result.count("pass") == 2

    def test_preserves_imports(self):
        solution = (
            "from typing import List\n"
            "\n"
            "def first(items: List[int]) -> int:\n"
            "    return items[0]\n"
        )
        result = generate_template_from_solution(solution, "python")
        assert "from typing import List" in result
        assert "def first(items: List[int]) -> int:" in result
        assert "pass" in result

    def test_class_with_property_annotation(self):
        solution = (
            "class Person:\n"
            "    name: str\n"
            "    age: int = 0\n"
            "\n"
            "    def __init__(self, name: str):\n"
            "        self.name = name\n"
        )
        result = generate_template_from_solution(solution, "python")
        assert "name: str" in result
        assert "age: int = 0" in result
        assert "def __init__(self, name: str):" in result


# ---------------------------------------------------------------------------
# TypeScript / JavaScript
# ---------------------------------------------------------------------------

class TestTypeScriptTemplate:
    def test_standalone_function(self):
        solution = "function add(a: number, b: number): number {\n  return a + b;\n}"
        result = generate_template_from_solution(solution, "typescript")
        assert "function add(a: number, b: number): number {" in result
        assert "// TODO: implement" in result
        assert "return a + b" not in result

    def test_class_with_constructor_and_methods(self):
        solution = (
            "class Vehicle {\n"
            '  private brand: string;\n'
            "  static count: number = 0;\n"
            "\n"
            "  constructor(brand: string) {\n"
            '    this.brand = brand;\n'
            "    Vehicle.count++;\n"
            "  }\n"
            "\n"
            "  getBrand(): string {\n"
            '    return this.brand;\n'
            "  }\n"
            "\n"
            "  static getVehicleCount(): number {\n"
            "    return Vehicle.count;\n"
            "  }\n"
            "}\n"
        )
        result = generate_template_from_solution(solution, "typescript")
        assert "class Vehicle {" in result
        assert "private brand: string;" in result
        assert "static count: number = 0;" in result
        assert "constructor(brand: string) {" in result
        assert "getBrand(): string {" in result
        assert "static getVehicleCount(): number {" in result
        assert "// TODO: implement" in result
        # Implementation should be stripped
        assert "this.brand" not in result
        assert "Vehicle.count++" not in result

    def test_enum_in_solution(self):
        solution = (
            "enum Status { Active, Inactive }\n"
            "\n"
            "function isActive(s: Status): boolean {\n"
            "  return s === Status.Active;\n"
            "}\n"
        )
        result = generate_template_from_solution(solution, "typescript")
        assert "enum Status { Active, Inactive }" in result
        assert "function isActive(s: Status): boolean {" in result
        assert "// TODO: implement" in result

    def test_interface_preserved(self):
        solution = (
            "interface Shape {\n"
            "  area(): number;\n"
            "}\n"
            "\n"
            "class Circle implements Shape {\n"
            "  radius: number;\n"
            "\n"
            "  constructor(radius: number) {\n"
            "    this.radius = radius;\n"
            "  }\n"
            "\n"
            "  area(): number {\n"
            "    return Math.PI * this.radius * this.radius;\n"
            "  }\n"
            "}\n"
        )
        result = generate_template_from_solution(solution, "typescript")
        assert "interface Shape {" in result
        assert "class Circle implements Shape {" in result
        assert "radius: number;" in result
        assert "constructor(radius: number) {" in result
        assert "area(): number {" in result


class TestJavaScriptTemplate:
    def test_standalone_function(self):
        solution = "function add(a, b) {\n  return a + b;\n}"
        result = generate_template_from_solution(solution, "javascript")
        assert "function add(a, b) {" in result
        assert "// TODO: implement" in result

    def test_class_with_methods(self):
        solution = (
            "class BankAccount {\n"
            "  constructor(balance) {\n"
            "    this.balance = balance;\n"
            "  }\n"
            "\n"
            "  deposit(amount) {\n"
            "    this.balance += amount;\n"
            "  }\n"
            "}\n"
        )
        result = generate_template_from_solution(solution, "javascript")
        assert "class BankAccount {" in result
        assert "constructor(balance) {" in result
        assert "deposit(amount) {" in result
        assert "// TODO: implement" in result
        assert "this.balance" not in result


# ---------------------------------------------------------------------------
# C++
# ---------------------------------------------------------------------------

class TestCppTemplate:
    def test_standalone_function(self):
        solution = "int add(int a, int b) {\n    return a + b;\n}"
        result = generate_template_from_solution(solution, "cpp")
        assert "int add(int a, int b) {" in result
        assert "// TODO: implement" in result
        assert "return 0;" in result
        assert "return a + b" not in result

    def test_class_with_methods(self):
        solution = (
            "class Vehicle {\n"
            "private:\n"
            "    std::string brand;\n"
            "    static int count;\n"
            "public:\n"
            "    Vehicle(std::string b) : brand(b) {\n"
            "        count++;\n"
            "    }\n"
            "    std::string getBrand() {\n"
            "        return brand;\n"
            "    }\n"
            "    static int getVehicleCount() {\n"
            "        return count;\n"
            "    }\n"
            "};\n"
        )
        result = generate_template_from_solution(solution, "cpp")
        assert "class Vehicle {" in result
        assert "private:" in result
        assert "std::string brand;" in result
        assert "static int count;" in result
        assert "public:" in result
        assert "Vehicle(std::string b) : brand(b) {" in result
        assert "getBrand()" in result
        assert "getVehicleCount()" in result
        assert "// TODO: implement" in result

    def test_struct_with_fields(self):
        solution = (
            "struct Point {\n"
            "    double x;\n"
            "    double y;\n"
            "    double distance() {\n"
            "        return sqrt(x*x + y*y);\n"
            "    }\n"
            "};\n"
        )
        result = generate_template_from_solution(solution, "cpp")
        assert "struct Point {" in result
        assert "double x;" in result
        assert "double y;" in result
        assert "distance()" in result
        assert "sqrt" not in result

    def test_preserves_includes(self):
        solution = (
            '#include <string>\n'
            '#include <cmath>\n'
            '\n'
            'double square(double x) {\n'
            '    return x * x;\n'
            '}\n'
        )
        result = generate_template_from_solution(solution, "cpp")
        assert "#include <string>" in result
        assert "#include <cmath>" in result
        assert "square(double x)" in result


# ---------------------------------------------------------------------------
# C
# ---------------------------------------------------------------------------

class TestCTemplate:
    def test_standalone_function(self):
        solution = "int add(int a, int b) {\n    return a + b;\n}"
        result = generate_template_from_solution(solution, "c")
        assert "int add(int a, int b) {" in result
        assert "/* TODO: implement */" in result or "// TODO: implement" in result
        assert "return 0;" in result

    def test_preserves_includes(self):
        solution = (
            '#include <stdio.h>\n'
            '#include <string.h>\n'
            '\n'
            'int len(const char* s) {\n'
            '    return strlen(s);\n'
            '}\n'
        )
        result = generate_template_from_solution(solution, "c")
        assert "#include <stdio.h>" in result
        assert "#include <string.h>" in result
        assert "len(const char* s)" in result

    def test_struct_with_function(self):
        solution = (
            "struct Point {\n"
            "    double x;\n"
            "    double y;\n"
            "};\n"
            "\n"
            "double distance(struct Point p) {\n"
            "    return sqrt(p.x*p.x + p.y*p.y);\n"
            "}\n"
        )
        result = generate_template_from_solution(solution, "c")
        assert "struct Point {" in result
        assert "double x;" in result
        assert "double y;" in result
        assert "distance(struct Point p)" in result


# ---------------------------------------------------------------------------
# Bash
# ---------------------------------------------------------------------------

class TestBashTemplate:
    def test_standalone_function(self):
        solution = "add() {\n  echo $(( $1 + $2 ))\n}"
        result = generate_template_from_solution(solution, "bash")
        assert "add() {" in result
        assert "# TODO: implement" in result
        assert "echo" not in result

    def test_multiple_functions(self):
        solution = (
            "add() {\n"
            "  echo $(( $1 + $2 ))\n"
            "}\n"
            "\n"
            "sub() {\n"
            "  echo $(( $1 - $2 ))\n"
            "}\n"
        )
        result = generate_template_from_solution(solution, "bash")
        assert "add() {" in result
        assert "sub() {" in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_unsupported_language_returns_solution(self):
        solution = "fn add(a: i32, b: i32) -> i32 { a + b }"
        result = generate_template_from_solution(solution, "rust")
        assert result == solution

    def test_empty_solution(self):
        result = generate_template_from_solution("", "python")
        assert result == ""

    def test_solution_with_only_comments(self):
        solution = "# This is a comment\n"
        result = generate_template_from_solution(solution, "python")
        assert result == solution.rstrip()

    def test_verify_signatures_still_works(self):
        from services.template_generator import verify_signatures_in_solution
        from services.exercise_schema import FunctionSignature

        sigs = [FunctionSignature(name="add", params="a, b", return_type="")]
        assert verify_signatures_in_solution(sigs, "def add(a, b):\n    return a + b")
        assert not verify_signatures_in_solution(sigs, "def multiply(a, b):\n    return a * b")
