import json
import pytest


class TestMarkdownToCells:
    """Unit tests for _markdown_to_cells conversion function."""

    def test_empty_markdown(self):
        """Empty markdown produces an empty cell list."""
        from services.outline_service import _markdown_to_cells
        result = _markdown_to_cells("")
        cells = json.loads(result)
        assert isinstance(cells, list)
        assert len(cells) == 0

    def test_markdown_with_code_block(self):
        """Markdown with code fences produces both markdown and code cells."""
        from services.outline_service import _markdown_to_cells
        md = "## Section\n\nSome text here.\n\n```python\nprint('hello')\n```\n\nMore text."
        result = _markdown_to_cells(md)
        cells = json.loads(result)
        types = [c["type"] for c in cells]
        assert "code" in types
        assert "markdown" in types

    def test_invalid_python_becomes_markdown_with_fences(self):
        """Python code with syntax errors should become a markdown cell preserving fences."""
        from services.outline_service import _markdown_to_cells
        md = "```python\nif True print('bad syntax')\n```"
        result = _markdown_to_cells(md)
        cells = json.loads(result)
        assert len(cells) == 1
        assert cells[0]["type"] == "markdown"
        assert "```python" in cells[0]["content"]
        assert "print" in cells[0]["content"]

    def test_valid_python_stays_python(self):
        """Valid Python code should remain a python cell."""
        from services.outline_service import _markdown_to_cells
        md = '```python\nprint("hello world")\n```'
        result = _markdown_to_cells(md)
        cells = json.loads(result)
        assert len(cells) == 1
        assert cells[0]["type"] == "code"
        assert cells[0]["language"] == "python"


class TestValidateSyntax:
    """Unit tests for _validate_syntax."""

    def test_valid_python(self):
        from services.outline_service import _validate_syntax
        assert _validate_syntax("python", 'print("hello")')
        assert _validate_syntax("python", 'x = 1\ny = 2\nprint(x + y)')
        assert _validate_syntax("python", 'def foo():\n    return 42\n\nprint(foo())')

    def test_invalid_python(self):
        from services.outline_service import _validate_syntax
        assert not _validate_syntax("python", "if True print('x')")
        assert not _validate_syntax("python", "for i in range(10) print(i)")

    def test_empty_code(self):
        from services.outline_service import _validate_syntax
        assert not _validate_syntax("python", "")
        assert not _validate_syntax("javascript", "")

    def test_unknown_language_passes(self):
        """Unknown languages pass validation (no checker available)."""
        from services.outline_service import _validate_syntax
        assert _validate_syntax("unknown_lang", "some code")

    # ── JavaScript ──

    def test_valid_javascript(self):
        from services.outline_service import _validate_syntax
        assert _validate_syntax("javascript", "console.log('hello');")
        assert _validate_syntax("javascript", "const x = 1;\nconst y = 2;\nconsole.log(x + y);")
        assert _validate_syntax("javascript", "function add(a, b) {\n  return a + b;\n}\nconsole.log(add(1, 2));")

    def test_invalid_javascript(self):
        from services.outline_service import _validate_syntax
        assert not _validate_syntax("javascript", "if true {")
        assert not _validate_syntax("javascript", "const x = ;")

    # ── TypeScript ──

    def test_valid_typescript(self):
        from services.outline_service import _validate_syntax
        assert _validate_syntax("typescript", "const x: number = 1;\nconsole.log(x);")

    def test_invalid_typescript(self):
        from services.outline_service import _validate_syntax
        assert not _validate_syntax("typescript", "const x: ;")

    # ── Bash ──

    def test_valid_bash(self):
        from services.outline_service import _validate_syntax
        assert _validate_syntax("bash", "echo hello")

    def test_invalid_bash(self):
        from services.outline_service import _validate_syntax
        assert not _validate_syntax("bash", "if then fi")

    # ── C ──

    def test_valid_c(self):
        from services.outline_service import _validate_syntax
        code = '#include <stdio.h>\nint main() { printf("hello\\n"); return 0; }'
        assert _validate_syntax("c", code)

    def test_invalid_c(self):
        from services.outline_service import _validate_syntax
        assert not _validate_syntax("c", "int main() { printf(")

    # ── C++ ──

    def test_valid_cpp(self):
        from services.outline_service import _validate_syntax
        code = '#include <iostream>\nint main() { std::cout << "hello" << std::endl; return 0; }'
        assert _validate_syntax("cpp", code)

    def test_invalid_cpp(self):
        from services.outline_service import _validate_syntax
        assert not _validate_syntax("cpp", "int main() { cout << << ")

    # ── Shell (alias for bash) ──

    def test_valid_shell(self):
        from services.outline_service import _validate_syntax
        assert _validate_syntax("shell", "echo hello")

    def test_invalid_shell(self):
        from services.outline_service import _validate_syntax
        assert not _validate_syntax("shell", "if then fi")

    # ── PowerShell ──

    def test_valid_powershell(self):
        from services.outline_service import _validate_syntax
        assert _validate_syntax("powershell", "Write-Host 'hello'")
        assert _validate_syntax("powershell", "$x = 1\n$x")

    def test_invalid_powershell(self):
        from services.outline_service import _validate_syntax
        assert not _validate_syntax("powershell", "if (true) {")

    # ── cmd/bat — always pass (no syntax-only checker exists) ──

    def test_cmd_always_passes(self):
        from services.outline_service import _validate_syntax
        assert _validate_syntax("cmd", "invalid stuff")

    # ── encoding ──

    def test_valid_syntax_with_utf8_output(self):
        """Syntax check should handle UTF-8 output from tools (no UnicodeDecodeError)."""
        import subprocess
        from unittest.mock import patch
        from services.outline_service import _validate_syntax

        # Simulate a real node --check that outputs UTF-8 characters
        mock_result = subprocess.CompletedProcess(
            args=["node", "--check", "test.js"],
            returncode=0,
            stdout="",
            stderr="",
        )
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = _validate_syntax("javascript", "const x = 1;")
            assert result is True
            # Verify encoding=utf-8 was passed
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("encoding") == "utf-8"
            assert call_kwargs.get("errors") == "replace"
