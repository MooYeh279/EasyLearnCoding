import pytest
from unittest.mock import patch, MagicMock
from services.env_checker import check_environment, LanguageEnvironment


class TestCheckEnvironment:
    def test_python_detected(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Python 3.11.7\n")
            result = check_environment("python")
            assert result.language == "python"
            assert result.runtime_available is True
            assert "3.11.7" in result.version

    def test_runtime_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = check_environment("python", force=True)
            assert result.runtime_available is False
            assert result.version is None

    def test_gcc_detected(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="gcc (MinGW) 13.1.0\n")
            result = check_environment("c")
            assert result.language == "c"
            assert result.runtime_available is True
            assert "13.1.0" in result.version

    def test_node_detected(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="v20.10.0\n")
            result = check_environment("javascript")
            assert result.runtime_available is True
            assert "20.10.0" in result.version

    def test_unsupported_language_raises(self):
        with pytest.raises(ValueError, match="Unsupported language"):
            check_environment("rust")
