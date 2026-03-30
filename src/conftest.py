import os
import socket
import subprocess
import time
from contextlib import closing

import pkg_resources
import pytest
import yaml

import cnaas_nms.api.app
from cnaas_nms.api.tests.app_wrapper import TestAppWrapper
from cnaas_nms.scheduler.scheduler import Scheduler


def pytest_configure(config):
    # Disable JWT tokens during unit testing (since app defaults want to load from global paths)
    from cnaas_nms.app_settings import api_settings, app_settings

    api_settings.JWT_ENABLED = False
    app_settings.TEMPLATES_REMOTE = "https://github.com/SUNET/cnaas-integrationtest-templates.git"
    app_settings.SETTINGS_REMOTE = "https://github.com/SUNET/cnaas-integrationtest-settings.git"


@pytest.fixture(scope="session")
def settings_directory():
    """Configure settings path from environment variable.

    Set SETTINGS_LOCAL to a pre-cloned settings repository path.
    """
    from cnaas_nms.app_settings import app_settings

    external_path = os.getenv("SETTINGS_LOCAL")
    if external_path:
        if not os.path.isdir(external_path):
            raise ValueError(f"SETTINGS_LOCAL path does not exist: {external_path}")
        app_settings.SETTINGS_LOCAL = external_path
        return external_path

    if not os.path.isdir(app_settings.SETTINGS_LOCAL):
        raise ValueError(
            f"Settings directory not found: {app_settings.SETTINGS_LOCAL}. "
            "Set SETTINGS_LOCAL to a pre-cloned settings repository."
        )
    return app_settings.SETTINGS_LOCAL


@pytest.fixture
def mock_get_settings(monkeypatch):
    from cnaas_nms.db import settings

    original_get_settings = settings.get_settings

    mocks = {}

    def _mock(hostname: str, mock_response={}):
        """Register a mock for a given hostname."""
        mocks[hostname] = mock_response

    def fake_get_settings(dev=None, *args, **kwargs):
        if dev and dev.hostname in mocks:
            return mocks[dev.hostname], {}

        return original_get_settings(dev)

    monkeypatch.setattr("cnaas_nms.api.device.get_settings", fake_get_settings)

    return _mock


@pytest.fixture(scope="session")
def templates_directory():
    """Configure templates path from environment variable.

    Set TEMPLATES_LOCAL to a pre-cloned templates repository path.
    """
    from cnaas_nms.app_settings import app_settings

    external_path = os.getenv("TEMPLATES_LOCAL")
    if external_path:
        if not os.path.isdir(external_path):
            raise ValueError(f"TEMPLATES_LOCAL path does not exist: {external_path}")
        app_settings.TEMPLATES_LOCAL = external_path
        return external_path

    if not os.path.isdir(app_settings.TEMPLATES_LOCAL):
        raise ValueError(
            f"Templates directory not found: {app_settings.TEMPLATES_LOCAL}. "
            "Set TEMPLATES_LOCAL to a pre-cloned templates repository."
        )
    return app_settings.TEMPLATES_LOCAL


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig, request):
    """
    Set target docker-compose file to docker/docker-compose_pytest.yaml.

    A pytest-docker fixture.
    """

    return os.path.join(str(pytestconfig.rootdir), "docker", "docker-compose_pytest.yaml")


@pytest.fixture(scope="session")
def redis(docker_ip, request):
    """Start Redis with pytest-docker if not EXTERNAL_TEST_CONTAINERS is set."""
    use_external = os.getenv("EXTERNAL_TEST_CONTAINERS", "0").strip().lower() in (
        "1",
        "on",
        "yes",
        "true",
    )

    if not use_external:
        print("Using internal Redis (pytest-docker)")
        docker_services = request.getfixturevalue("docker_services")
        host = docker_ip
        port = docker_services.port_for("cnaas_redis", 6379)

        assert wait_for_port(host, port), f"Could not connect to Redis at {host}:{port}"

    time.sleep(1)

    yield True


@pytest.fixture(scope="session")
def postgresql(docker_ip, request):
    """Start PostgreSQL with pytest-docker if not EXTERNAL_TEST_CONTAINERS is set."""
    use_external = os.getenv("EXTERNAL_TEST_CONTAINERS", "0").strip().lower() in (
        "1",
        "on",
        "yes",
        "true",
    )

    if not use_external:
        print("Using PostgreSQL with pytest-docker")
        docker_services = request.getfixturevalue("docker_services")
        host, port = docker_ip, docker_services.port_for("cnaas_postgres", 5432)
        assert wait_for_port(host, port), f"Could not connect to PostgreSQL at {host}:{port}"
    else:
        time.sleep(5)

    request.getfixturevalue("alembic_upgrade")

    yield True


@pytest.fixture(scope="session")
def alembic_upgrade(pytestconfig):
    """Ensure sql database schema is up-to-date at the start of a test run."""
    subprocess.check_call(["alembic", "upgrade", "head"], cwd=pytestconfig.rootpath)


def wait_for_port(host: str, port: int, tries=10) -> bool:
    """Wait for TCP port to receive connections."""
    for _retry in range(tries):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            if sock.connect_ex((host, port)) == 0:
                print(f"{host}:{port} responded")
                time.sleep(1)  # port open != service ready, so wait slightly longer
                return True
        time.sleep(0.5)
    print(f"NO RESPONSE from {host}:{port}")
    return False


@pytest.fixture(scope="session")
def scheduler():
    scheduler = Scheduler()
    scheduler.start()
    yield scheduler
    time.sleep(3)
    scheduler.get_scheduler().print_jobs()
    scheduler.shutdown()


@pytest.fixture
def client(app, redis, postgresql, settings_directory):
    return app.test_client()


@pytest.fixture
def app(jwt_auth_token):
    the_app = cnaas_nms.api.app.app
    the_app.wsgi_app = TestAppWrapper(the_app.wsgi_app, jwt_auth_token)
    return the_app


@pytest.fixture
def jwt_auth_token(testdata):
    return testdata.get("jwt_auth_token")


@pytest.fixture
def testdata(scope="session"):
    data_dir = pkg_resources.resource_filename(__name__, "cnaas_nms/api/tests/data")
    with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
        return yaml.safe_load(f_testdata)
