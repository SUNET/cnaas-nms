from pathlib import Path

import pytest
from flask.testing import FlaskClient
from git import Repo

from cnaas_nms.api import app
from cnaas_nms.api.tests.app_wrapper import TestAppWrapper
from cnaas_nms.app_settings import app_settings
from cnaas_nms.version import __version__


@pytest.fixture
def testclient(testdata: dict, scope="module") -> FlaskClient:
    nms_app = app.app
    nms_app.wsgi_app = TestAppWrapper(nms_app.wsgi_app, testdata["jwt_auth_token"])
    return nms_app.test_client()


def test_system_version(testclient: FlaskClient):
    result = testclient.get("/api/v1.0/system/version")
    assert result.status_code == 200

    data = result.json.get("data", {})

    repo = Repo(Path(__file__).resolve().parents[4])
    commit = repo.head.commit

    assert "version" in data
    assert "git_version" in data
    assert data["version"] == __version__
    # Check that the local repo info is in git_version string
    assert commit.name_rev in data["git_version"]


def test_system_with_overrides(testclient: FlaskClient, monkeypatch):
    monkeypatch.setattr(app_settings, "GIT_BRANCH", "custom_branch")
    monkeypatch.setattr(app_settings, "GIT_COMMIT", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    monkeypatch.setattr(app_settings, "GIT_DATE", "2026-04-16 18:31:05+02:00")

    result = testclient.get("/api/v1.0/system/version")
    assert result.status_code == 200
    data = result.json.get("data", {})

    assert data["version"] == __version__
    assert (
        data["git_version"]
        == "Git commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa custom_branch (2026-04-16 18:31:05+02:00)"
    )
