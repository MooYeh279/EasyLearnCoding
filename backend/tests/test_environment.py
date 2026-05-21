from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch
from models import Language
from services.env_checker import LanguageEnvironment

client = TestClient(app)


class TestEnvironmentAPI:
    def test_get_environment_python(self, db):
        db.add(Language(name="python", display_name="Python"))
        db.commit()
        with patch("routers.environment.check_environment") as mock_check:
            mock_check.return_value = LanguageEnvironment(
                language="python", runtime_available=True,
                version="3.11.7", runtime_path="python",
                package_manager="pip", package_manager_ok=True,
            )
            res = client.get("/api/environment/python")
            assert res.status_code == 200
            data = res.json()
            assert data["language"] == "python"
            assert data["runtime_available"] is True
            assert data["version"] == "3.11.7"

    def test_get_environment_unsupported(self):
        res = client.get("/api/environment/rust")
        assert res.status_code == 404

    def test_put_environment_config(self, db):
        db.add(Language(name="python", display_name="Python"))
        db.commit()
        res = client.put("/api/environment/python", json={"runtime_path": "/custom/python"})
        assert res.status_code == 200
        data = res.json()
        assert data["message"] == "Config updated"
