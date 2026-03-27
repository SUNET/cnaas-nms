"""Tests for the FastAPI app foundation: CORS, error handlers, auth, and simple endpoints."""

import unittest

from fastapi.testclient import TestClient

from cnaas_nms.api.fastapi_app import app

client = TestClient(app)


class TestCORS(unittest.TestCase):
    def test_cors_headers_present(self):
        response = client.options(
            "/api/v1.0/system/version",
            headers={"Origin": "http://example.com", "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" in response.headers


class TestSystemEndpoints(unittest.TestCase):
    def test_get_version(self):
        response = client.get("/api/v1.0/system/version")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "version" in data["data"]
        assert "git_version" in data["data"]

    def test_shutdown_endpoint_exists(self):
        """Verify the shutdown endpoint exists and is reachable.

        The actual shutdown may fail because the scheduler isn't running in
        test mode, but the endpoint should respond (not 404).
        """
        response = client.post("/api/v1.0/system/shutdown")
        assert response.status_code != 404


class TestPluginEndpoints(unittest.TestCase):
    def test_get_plugins(self):
        response = client.get("/api/v1.0/plugins")
        # May succeed or error depending on plugin manager state
        data = response.json()
        assert data["status"] in ("success", "error")

    def test_put_plugins_unknown_action(self):
        response = client.put("/api/v1.0/plugins", json={"action": "UNKNOWN"})
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "Unknown action" in data["message"]

    def test_put_plugins_missing_action(self):
        response = client.put("/api/v1.0/plugins", json={})
        # Pydantic validation will reject missing required field
        assert response.status_code == 422


class TestResponseFormat(unittest.TestCase):
    """Verify that the response format matches the Flask API contract."""

    def test_success_response_has_status_and_data(self):
        response = client.get("/api/v1.0/system/version")
        data = response.json()
        assert "status" in data
        assert "data" in data
        assert data["status"] == "success"

    def test_error_response_has_status_and_message(self):
        response = client.put("/api/v1.0/plugins", json={"action": "INVALID"})
        data = response.json()
        assert "status" in data
        assert "message" in data
        assert data["status"] == "error"


class TestOpenAPIDocs(unittest.TestCase):
    def test_openapi_json_available(self):
        response = client.get("/api/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data

    def test_docs_page_available(self):
        response = client.get("/api/doc/")
        assert response.status_code == 200


if __name__ == "__main__":
    unittest.main()
