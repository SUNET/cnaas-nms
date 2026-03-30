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
