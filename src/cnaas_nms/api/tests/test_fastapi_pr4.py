"""Tests for PR 4 FastAPI endpoints: interface and firmware."""

import unittest

from fastapi.testclient import TestClient

from cnaas_nms.api.fastapi_app import app

client = TestClient(app)


class TestInterfaceEndpoints(unittest.TestCase):
    def test_get_interfaces_device_not_found(self):
        response = client.get("/api/v1.0/device/nonexistent-host/interfaces")
        assert response.status_code == 404
        data = response.json()
        assert data["status"] == "error"
        assert "not found" in data["message"].lower()

    def test_put_interfaces_device_not_found(self):
        response = client.put(
            "/api/v1.0/device/nonexistent-host/interfaces",
            json={"interfaces": {"Ethernet1": {"configtype": "ACCESS_AUTO"}}},
        )
        assert response.status_code == 404

    def test_export_interfaces_device_not_found(self):
        response = client.get("/api/v1.0/device/nonexistent-host/interfaces_export")
        assert response.status_code == 404

    def test_interface_status_device_not_found(self):
        response = client.get("/api/v1.0/device/nonexistent-host/interface_status")
        # May return 400 (invalid input) or some other error since device doesn't exist
        assert response.status_code in (400, 404, 500)

    def test_bounce_interfaces_unknown_action(self):
        response = client.put(
            "/api/v1.0/device/nonexistent-host/interface_status",
            json={"invalid_key": "value"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"


class TestFirmwareEndpoints(unittest.TestCase):
    def test_post_firmware_missing_checksum(self):
        response = client.post(
            "/api/v1.0/firmware",
            json={"url": "http://example.com/fw.bin", "verify_tls": True},
        )
        data = response.json()
        assert data["status"] == "error"
        assert "checksum" in data["message"].lower()

    def test_post_firmware_missing_fields(self):
        response = client.post("/api/v1.0/firmware", json={})
        assert response.status_code == 422

    def test_upgrade_url_type_validation(self):
        response = client.post(
            "/api/v1.0/firmware/upgrade",
            json={"url": 12345, "hostname": "testhost"},
        )
        # url is not a string, should return error
        data = response.json()
        assert data["status"] == "error"
        assert "string" in data["message"].lower()

    def test_upgradecheck_missing_group(self):
        response = client.post("/api/v1.0/firmware/upgradecheck", json={})
        assert response.status_code == 422


class TestOpenAPIInclusion(unittest.TestCase):
    def test_interface_in_openapi(self):
        response = client.get("/api/openapi.json")
        paths = response.json()["paths"]
        assert any("interfaces" in path for path in paths)

    def test_firmware_in_openapi(self):
        response = client.get("/api/openapi.json")
        paths = response.json()["paths"]
        assert any("firmware" in path for path in paths)


if __name__ == "__main__":
    unittest.main()
