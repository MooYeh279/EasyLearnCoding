"""Tests for code_executor.py — execution and typecheck paths."""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestRunCodeEndpoint:
    """End-to-end code execution tests via TestClient."""

    def test_python_executes(self):
        r = client.post("/api/code/run", json={"code": "print('hello')", "language": "python"})
        assert r.status_code == 200
        data = r.json()
        assert "hello" in data["stdout"]
        assert data["exit_code"] == 0

    def test_python_eval_executes(self):
        """eval(), exec(), open() are no longer blocked — students may learn these topics."""
        r = client.post("/api/code/run", json={"code": "print(eval('1+1'))", "language": "python"})
        assert r.status_code == 200
        data = r.json()
        assert data["exit_code"] == 0
        assert "2" in data["stdout"]

    def test_javascript_executes(self):
        r = client.post("/api/code/run", json={"code": "console.log('js ok')", "language": "javascript"})
        assert r.status_code == 200
        data = r.json()
        assert "js ok" in data["stdout"]
        assert data["exit_code"] == 0

    def test_bash_executes(self):
        r = client.post("/api/code/run", json={"code": "echo bash ok", "language": "bash"})
        assert r.status_code == 200
        data = r.json()
        assert "bash ok" in data["stdout"]
        assert data["exit_code"] == 0

    def test_typescript_valid_passes_typecheck(self):
        r = client.post("/api/code/run", json={
            "code": "const x: number = 42;\nconsole.log(x);",
            "language": "typescript"
        })
        assert r.status_code == 200
        data = r.json()
        assert "42" in data["stdout"]
        assert data["exit_code"] == 0

    def test_typescript_type_error_caught(self):
        r = client.post("/api/code/run", json={
            "code": "const x: number = 'not a number';\nconsole.log(x);",
            "language": "typescript"
        })
        assert r.status_code == 200
        data = r.json()
        assert data["exit_code"] != 0

    def test_unsupported_language_returns_400(self):
        r = client.post("/api/code/run", json={"code": "x", "language": "rust"})
        assert r.status_code == 400

    def test_code_too_long(self):
        r = client.post("/api/code/run", json={"code": "x" * 100_001, "language": "python"})
        assert r.status_code == 200
        data = r.json()
        assert data["exit_code"] == 1
