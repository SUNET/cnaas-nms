import os
import socket
import subprocess
import time
from contextlib import closing

import pytest
from git import Repo

from cnaas_nms.scheduler.scheduler import Scheduler


def pytest_configure(config):
    # Disable JWT tokens during unit testing (since app defaults want to load from global paths)
    from cnaas_nms.app_settings import api_settings, app_settings

    api_settings.JWT_ENABLED = False
    app_settings.TEMPLATES_REMOTE = "git://gitops.sunet.se/cnaas-lab-templates"
    app_settings.SETTINGS_REMOTE = "git://gitops.sunet.se/cnaas-lab-settings"


@pytest.fixture(scope="session")
def settings_directory(tmp_path_factory):
    from cnaas_nms.app_settings import app_settings

    if os.getenv("PYTEST_SETTINGS_CLONED", "0").strip() in ("0", "off", "false", "no"):
        settings_dir = tmp_path_factory.mktemp("settings")
        app_settings.SETTINGS_LOCAL = settings_dir
        print(f"placing settings in {settings_dir}")
        Repo.clone_from(app_settings.SETTINGS_REMOTE, app_settings.SETTINGS_LOCAL)
        return settings_dir
    else:
        return app_settings.SETTINGS_LOCAL


@pytest.fixture(scope="session")
def templates_directory(tmp_path_factory):
    from cnaas_nms.app_settings import app_settings

    if os.getenv("PYTEST_TEMPLATES_CLONED", "0").strip() in ("0", "off", "false", "no"):
        templates_dir = tmp_path_factory.mktemp("templates")
        app_settings.TEMPLATES_LOCAL = templates_dir
        print(f"placing settings in {templates_dir}")
        Repo.clone_from(app_settings.TEMPLATES_REMOTE, app_settings.TEMPLATES_LOCAL)
        return templates_dir
    else:
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
