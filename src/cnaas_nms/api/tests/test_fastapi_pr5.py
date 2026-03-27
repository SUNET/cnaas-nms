"""Tests for PR 5-6 FastAPI endpoints: device (read + write)."""

import unittest

from fastapi.testclient import TestClient

from cnaas_nms.api.fastapi_app import app

client = TestClient(app)


class TestDeviceReadEndpoints(unittest.TestCase):
    """PR 5: Read-only device endpoints."""

    def test_get_device_by_id_not_found(self):
        response = client.get("/api/v1.0/device/999999")
        assert response.status_code == 404
        data = response.json()
        assert data["status"] == "error"

    def test_get_device_by_hostname_not_found(self):
        # Use a valid-looking hostname so it doesn't get caught by int parsing
        response = client.get("/api/v1.0/device/nonexistent-host")
        # FastAPI tries /device/{device_id} first (int), then /device/{hostname}
        # "nonexistent-host" is not an int so FastAPI returns 404 (hostname route)
        assert response.status_code in (404, 422)  # 422 if int route matches first

    def test_get_generate_config_invalid_hostname(self):
        response = client.get("/api/v1.0/device/not valid!!!/generate_config")
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "invalid hostname" in data["message"].lower()

    def test_get_running_config_invalid_hostname(self):
        response = client.get("/api/v1.0/device/not valid!!!/running_config")
        assert response.status_code == 400

    def test_get_lldp_neighbors_invalid_hostname(self):
        response = client.get("/api/v1.0/device/not valid!!!/lldp_neighbors")
        assert response.status_code == 400

    def test_get_lldp_neighbors_detail_invalid_hostname(self):
        response = client.get("/api/v1.0/device/not valid!!!/lldp_neighbors_detail")
        assert response.status_code == 400

    def test_get_previous_config_not_found(self):
        response = client.get("/api/v1.0/device/nonexistent-host/previous_config")
        assert response.status_code == 404

    def test_get_stackmembers_not_found(self):
        response = client.get("/api/v1.0/device/nonexistent-host/stackmembers")
        # May be 404 or 500 depending on DB access
        assert response.status_code in (404, 500)


class TestDeviceWriteEndpoints(unittest.TestCase):
    """PR 6: Write device endpoints."""

    def test_delete_device_not_found(self):
        response = client.delete("/api/v1.0/device/999999")
        assert response.status_code == 404

    def test_put_device_not_found(self):
        response = client.put("/api/v1.0/device/999999", json={"hostname": "test"})
        assert response.status_code == 404

    def test_post_device_missing_fields(self):
        response = client.post("/api/v1.0/devices", json={})
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"

    def test_post_device_invalid_platform(self):
        response = client.post(
            "/api/v1.0/devices",
            json={
                "hostname": "testdevice",
                "platform": "unsupported",
                "state": "MANAGED",
                "device_type": "ACCESS",
            },
        )
        assert response.status_code == 400

    def test_init_device_missing_hostname(self):
        response = client.post("/api/v1.0/device_init/999999", json={})
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"

    def test_init_device_missing_device_type(self):
        response = client.post("/api/v1.0/device_init/999999", json={"hostname": "testhost"})
        assert response.status_code == 400

    def test_initcheck_missing_args(self):
        response = client.post("/api/v1.0/device_initcheck/999999", json={})
        assert response.status_code == 400

    def test_discover_missing_ztp_mac(self):
        response = client.post("/api/v1.0/device_discover", json={})
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "ztp_mac" in data["message"].lower()

    def test_syncto_in_openapi(self):
        """Verify syncto endpoints are registered via OpenAPI spec."""
        response = client.get("/api/openapi.json")
        paths = response.json()["paths"]
        assert any("device_syncto" in path for path in paths)

    def test_update_facts_no_hostname(self):
        response = client.post("/api/v1.0/device_update_facts", json={})
        assert response.status_code == 400

    def test_update_facts_invalid_hostname(self):
        response = client.post("/api/v1.0/device_update_facts", json={"hostname": "not valid!!!"})
        assert response.status_code == 400

    def test_update_interfaces_no_hostname(self):
        response = client.post("/api/v1.0/device_update_interfaces", json={})
        assert response.status_code == 400

    def test_cert_missing_action(self):
        response = client.post("/api/v1.0/device_cert", json={})
        assert response.status_code == 400

    def test_synchistory_get_not_found(self):
        response = client.get("/api/v1.0/device/nonexistent-host/synchistory")
        # Returns empty or 404
        assert response.status_code in (200, 404)

    def test_apply_config_missing_config(self):
        response = client.post(
            "/api/v1.0/device/testhost/apply_config",
            json={},
        )
        # Missing full_config should error
        assert response.status_code in (400, 422, 500)


class TestDeviceResponseFormat(unittest.TestCase):
    def test_device_error_format(self):
        response = client.get("/api/v1.0/device/999999")
        data = response.json()
        assert "status" in data
        assert data["status"] == "error"


class TestDeviceOpenAPI(unittest.TestCase):
    def test_device_endpoints_in_openapi(self):
        response = client.get("/api/openapi.json")
        paths = response.json()["paths"]
        assert any("device" in path for path in paths)
        assert any("devices" in path for path in paths)

    def test_device_syncto_in_openapi(self):
        response = client.get("/api/openapi.json")
        paths = response.json()["paths"]
        assert any("syncto" in path for path in paths)

    def test_device_init_in_openapi(self):
        response = client.get("/api/openapi.json")
        paths = response.json()["paths"]
        assert any("device_init" in path for path in paths)


if __name__ == "__main__":
    unittest.main()
