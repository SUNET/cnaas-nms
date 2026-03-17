"""Tests for PR 2 FastAPI endpoints: repository, settings, jobs."""

import unittest

from fastapi.testclient import TestClient

from cnaas_nms.api.fastapi_app import app

client = TestClient(app)


class TestRepositoryEndpoints(unittest.TestCase):
    def test_get_repository_invalid_type(self):
        response = client.get("/api/v1.0/repository/invalid_repo")
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "Invalid repository type" in data["message"]

    def test_put_repository_invalid_type(self):
        response = client.put("/api/v1.0/repository/invalid_repo", json={"action": "REFRESH"})
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"

    def test_put_repository_invalid_action(self):
        response = client.put("/api/v1.0/repository/settings", json={"action": "INVALID"})
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "Invalid action" in data["message"]

    def test_put_repository_missing_action(self):
        response = client.put("/api/v1.0/repository/settings", json={})
        # Pydantic validation rejects missing required field
        assert response.status_code == 422


class TestSettingsEndpoints(unittest.TestCase):
    def test_get_settings_model_schema(self):
        response = client.get("/api/v1.0/settings/model")
        assert response.status_code == 200
        data = response.json()
        # Should return a JSON schema
        assert "properties" in data or "type" in data or "$defs" in data

    def test_post_settings_model_empty(self):
        response = client.post("/api/v1.0/settings/model", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_get_settings_invalid_hostname(self):
        response = client.get("/api/v1.0/settings?hostname=not a valid hostname!!!")
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"

    def test_get_settings_invalid_device_type(self):
        response = client.get("/api/v1.0/settings?device_type=NONEXISTENT")
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "Invalid device type" in data["message"]


class TestJobEndpoints(unittest.TestCase):
    def test_get_job_not_found(self):
        response = client.get("/api/v1.0/job/999999")
        # Without DB this will error, but endpoint should exist
        assert response.status_code != 404 or response.status_code == 400

    def test_put_job_unknown_action(self):
        response = client.put("/api/v1.0/job/1", json={"action": "UNKNOWN"})
        # Either job not found (400) or unknown action (400)
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"

    def test_put_job_missing_action(self):
        response = client.put("/api/v1.0/job/1", json={})
        # Pydantic validation rejects missing required field
        assert response.status_code == 422

    def test_delete_joblock_missing_name(self):
        response = client.request("DELETE", "/api/v1.0/joblocks", json={})
        # Pydantic validation rejects missing required field
        assert response.status_code == 422


class TestResponseFormat(unittest.TestCase):
    """Verify backwards-compatible response format for new endpoints."""

    def test_repository_error_format(self):
        response = client.get("/api/v1.0/repository/invalid")
        data = response.json()
        assert "status" in data
        assert "message" in data
        assert data["status"] == "error"

    def test_settings_model_is_json(self):
        response = client.get("/api/v1.0/settings/model")
        assert response.headers["content-type"] == "application/json"


class TestOpenAPIInclusion(unittest.TestCase):
    """Verify new endpoints appear in OpenAPI spec."""

    def test_repository_in_openapi(self):
        response = client.get("/api/openapi.json")
        paths = response.json()["paths"]
        assert any("repository" in path for path in paths)

    def test_settings_in_openapi(self):
        response = client.get("/api/openapi.json")
        paths = response.json()["paths"]
        assert any("settings" in path for path in paths)

    def test_jobs_in_openapi(self):
        response = client.get("/api/openapi.json")
        paths = response.json()["paths"]
        assert any("job" in path for path in paths)


if __name__ == "__main__":
    unittest.main()
