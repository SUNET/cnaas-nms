"""Tests for PR 3 FastAPI endpoints: linknet and mgmtdomain."""

import unittest

from fastapi.testclient import TestClient

from cnaas_nms.api.fastapi_app import app

client = TestClient(app)


class TestLinknetEndpoints(unittest.TestCase):
    def test_get_linknet_not_found(self):
        response = client.get("/api/v1.0/linknet/999999")
        assert response.status_code == 404
        data = response.json()
        assert data["status"] == "error"
        assert "not found" in data["message"].lower()

    def test_delete_linknet_not_found(self):
        response = client.delete("/api/v1.0/linknet/999999")
        assert response.status_code == 404

    def test_create_linknet_invalid_hostname(self):
        response = client.post(
            "/api/v1.0/linknets",
            json={
                "device_a": "not valid!!!",
                "device_b": "also-not-valid!!!",
                "device_a_port": "eth0",
                "device_b_port": "eth1",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"

    def test_create_linknet_missing_fields(self):
        response = client.post("/api/v1.0/linknets", json={"device_a": "test"})
        # Pydantic validation rejects missing required fields
        assert response.status_code == 422

    def test_delete_linknet_by_body_missing_id(self):
        response = client.request("DELETE", "/api/v1.0/linknets", json={})
        assert response.status_code == 422

    def test_put_linknet_not_found(self):
        response = client.put("/api/v1.0/linknet/999999", json={"ipv4_network": "10.0.0.0/31"})
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"


class TestMgmtdomainEndpoints(unittest.TestCase):
    def test_get_mgmtdomain_not_found(self):
        response = client.get("/api/v1.0/mgmtdomain/999999")
        assert response.status_code == 404
        data = response.json()
        assert data["status"] == "error"
        assert "not found" in data["message"].lower()

    def test_delete_mgmtdomain_not_found(self):
        response = client.delete("/api/v1.0/mgmtdomain/999999")
        assert response.status_code == 404

    def test_create_mgmtdomain_invalid_hostname(self):
        response = client.post(
            "/api/v1.0/mgmtdomains",
            json={
                "device_a": "not valid!!!",
                "device_b": "also not valid!!!",
                "vlan": 100,
                "ipv4_gw": "10.0.0.1/24",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"

    def test_create_mgmtdomain_missing_fields(self):
        response = client.post("/api/v1.0/mgmtdomains", json={"device_a": "test"})
        assert response.status_code == 422

    def test_put_mgmtdomain_not_found(self):
        response = client.put("/api/v1.0/mgmtdomain/999999", json={"vlan": 200})
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"

    def test_put_mgmtdomain_invalid_ipv4(self):
        response = client.put("/api/v1.0/mgmtdomain/999999", json={"ipv4_gw": "not-an-ip"})
        assert response.status_code == 400


class TestPydanticValidation(unittest.TestCase):
    """Test that existing Pydantic models (f_linknet, f_mgmtdomain) still work."""

    def test_f_linknet_valid(self):
        from cnaas_nms.api.linknet import f_linknet

        obj = f_linknet(ipv4_network="10.0.0.0/31", device_a_ip="10.0.0.0", device_b_ip="10.0.0.1")
        assert obj.ipv4_network == "10.0.0.0/31"

    def test_f_linknet_invalid_prefix(self):
        from pydantic import ValidationError

        from cnaas_nms.api.linknet import f_linknet

        with self.assertRaises(ValidationError):
            f_linknet(ipv4_network="10.0.0.0/16")

    def test_f_mgmtdomain_valid(self):
        from cnaas_nms.api.mgmtdomain import f_mgmtdomain

        obj = f_mgmtdomain(vlan=100, ipv4_gw="10.0.0.1/24")
        assert obj.vlan == 100

    def test_f_mgmtdomain_invalid_gw(self):
        from pydantic import ValidationError

        from cnaas_nms.api.mgmtdomain import f_mgmtdomain

        with self.assertRaises(ValidationError):
            f_mgmtdomain(ipv4_gw="not-an-ip")


class TestOpenAPIInclusion(unittest.TestCase):
    def test_linknet_in_openapi(self):
        response = client.get("/api/openapi.json")
        paths = response.json()["paths"]
        assert any("linknet" in path for path in paths)

    def test_mgmtdomain_in_openapi(self):
        response = client.get("/api/openapi.json")
        paths = response.json()["paths"]
        assert any("mgmtdomain" in path for path in paths)


if __name__ == "__main__":
    unittest.main()
