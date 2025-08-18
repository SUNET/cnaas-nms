import os

import pkg_resources
import pytest
import yaml
from flask.testing import FlaskClient

from cnaas_nms.api import app
from cnaas_nms.api.tests.app_wrapper import TestAppWrapper


@pytest.fixture
def testdata(scope="module") -> dict:
    data_dir = pkg_resources.resource_filename(__name__, "data")
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


def test_settings_model(testclient: FlaskClient):
    result = testclient.get("/api/v1.0/settings/model")
    assert result.status_code == 200
    assert result.content_type == "application/json"
    assert "$defs" in result.json


def test_settings_server(testclient: FlaskClient):
    result = testclient.get("/api/v1.0/settings/server")
    assert result.status_code == 200
    assert result.content_type == "application/json"
    assert "api" in result.json
