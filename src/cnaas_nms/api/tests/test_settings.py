import os
from pathlib import Path

import pytest
import yaml
from flask.testing import FlaskClient

from cnaas_nms.api import app
from cnaas_nms.api.tests.app_wrapper import TestAppWrapper
from cnaas_nms.db.settings import FILE_MODEL_MAP


@pytest.fixture
def testdata(scope="module") -> dict:
    data_dir = Path(__file__).parent / "data"
    with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
        return yaml.safe_load(f_testdata)


@pytest.fixture
def testclient(testdata: dict, scope="module") -> FlaskClient:
    nms_app = app.app
    nms_app.wsgi_app = TestAppWrapper(nms_app.wsgi_app, testdata["jwt_auth_token"])
    return nms_app.test_client()


def test_invalid_setting(testclient: FlaskClient):
    settings_data = {"ntp_servers": [{"host": "10.0.0.500"}]}
    result = testclient.post("/api/v1.0/settings/model", json=settings_data)
    assert result.status_code == 400


def test_valid_setting(testclient: FlaskClient):
    settings_data = {"ntp_servers": [{"host": "10.0.0.50"}]}
    result = testclient.post("/api/v1.0/settings/model", json=settings_data)
    assert result.status_code == 200


def test_invalid_access_list_setting(testclient: FlaskClient):
    settings_data = {
        "access_lists": {"ACLTEST": {"terms": [{"action": "accept"}]}},
    }
    result = testclient.post("/api/v1.0/settings/model", json=settings_data)
    assert result.status_code == 400


@pytest.mark.integration
def test_valid_access_list_setting(testclient: FlaskClient):
    settings_data = {
        "access_lists": {"ACLTEST": {"terms": [{"name": "term_name", "action": "accept"}]}},
    }

    result = testclient.post("/api/v1.0/settings/model", json=settings_data)
    assert result.status_code == 200


def test_access_list_reference(testclient: FlaskClient):
    """Makes sure that access lists with jmespath references are able to generate without fully validating the jmespath."""
    settings_data = {
        "network_definitions": {
            "BGP_PEERS": [
                {"path": "extroute_bgp.vrfs[].neighbor_v4[].peer_ipv4"},
                {"path": "extroute_bgp.vrfs[].neighbor_v6[].peer_ipv6"},
            ]
        },
        "access_lists": {
            "ACLTEST": {"terms": [{"name": "allow_bgp", "destination-address": "BGP_PEERS", "action": "accept"}]}
        },
    }

    result = testclient.post("/api/v1.0/settings/model", json=settings_data)
    assert result.status_code == 200


def test_access_list_reference_no_data(testclient: FlaskClient):
    """
    When sending more data than just the access list with jmespath references,
    we want to make sure that we still validate that the access list generation fails when no valid data is sent to aerleon.
    """
    settings_data = {
        "extroute_bgp": {
            "vrfs": [
                {
                    "name": "OUTSIDE",
                    "local_as": 64667,
                    "neighbor_v4": [],
                }
            ]
        },
        "network_definitions": {
            "BGP_PEERS": [
                {"path": "extroute_bgp.vrfs[].neighbor_v4[].peer_ipv4"},
            ]
        },
        "access_lists": {
            "ACLTEST": {"terms": [{"name": "allow_bgp", "destination-address": "BGP_PEERS", "action": "accept"}]}
        },
    }

    result = testclient.post("/api/v1.0/settings/model", json=settings_data)

    assert result.status_code == 400
    assert "No IP addresses found for network: BGP_PEERS" in result.json["message"]


def test_access_list_reference_vxlans(testclient: FlaskClient):
    """Test that reference to vxlans falls back to standard values instead of being empty"""
    settings_data = {
        "network_definitions": {
            "students_gws": [
                {"path": "vxlans.* | [?vrf=='STUDENT'].[ipv4_gw, ipv4_secondaries, ipv6_gw][][]"},
            ]
        },
        "access_lists": {
            "ACLTEST": {"terms": [{"name": "allow_bgp", "destination-address": "students_gws", "action": "accept"}]}
        },
    }

    result = testclient.post("/api/v1.0/settings/model", json=settings_data)
    assert result.status_code == 200


def test_access_list_invalid_jmespath(testclient: FlaskClient):
    """Test that invalid jmespath triggers on /settings/model api"""
    settings_data = {
        "network_definitions": {
            "invalid_path": [
                {"path": "vxlans]"},
            ]
        }
    }

    result = testclient.post("/api/v1.0/settings/model", json=settings_data)
    assert result.status_code == 400


def test_settings_model(testclient: FlaskClient):
    result = testclient.get("/api/v1.0/settings/model")
    assert result.status_code == 200
    assert result.content_type == "application/json"
    assert "$defs" in result.json


def test_settings_model_name_good_filenames(testclient: FlaskClient):
    for filename in FILE_MODEL_MAP.keys():
        result = testclient.get(f"/api/v1.0/settings/model/{filename}")
        assert result.status_code == 200
        assert result.content_type == "application/json"
        assert "$defs" in result.json


def test_settings_model_name_bad_filename(testclient: FlaskClient):
    result = testclient.get("/api/v1.0/settings/model/some_other_file.yml")
    assert result.status_code == 400
    assert result.content_type == "application/json"


def test_settings_model_base_system_valid_setting(testclient: FlaskClient):
    settings_data = {"ntp_servers": [{"host": "10.0.0.50"}]}  # noqa: S1313
    result = testclient.post("/api/v1.0/settings/model/base_system.yml", json=settings_data)
    assert result.status_code == 200


def test_settings_model_base_system_invalid_setting(testclient: FlaskClient):
    settings_data = {
        "ntp_server": [{"host": "10.0.0.50"}],  # noqa: S1313
        "some_other_invalid_setting": [{"a": "b"}],
    }
    result = testclient.post("/api/v1.0/settings/model/base_system.yml", json=settings_data)
    assert result.status_code == 400


def test_settings_server(testclient: FlaskClient):
    result = testclient.get("/api/v1.0/settings/server")
    assert result.status_code == 200
    assert result.content_type == "application/json"
    assert "api" in result.json
