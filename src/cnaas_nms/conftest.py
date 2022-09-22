import time
import socket
from contextlib import closing

from git import Repo

import pytest


pytest_plugins = ["docker_compose"]


def pytest_configure(config):
    # Disable JWT tokens during unit testing (since app defaults want to load from global paths)
    from cnaas_nms.app_settings import api_settings, app_settings
    api_settings.JWT_ENABLED = False

    app_settings.TEMPLATES_REMOTE = "git://gitops.sunet.se/cnaas-lab-templates"
    app_settings.SETTINGS_REMOTE = "git://gitops.sunet.se/cnaas-lab-settings"


@pytest.fixture(scope="session")
def settings_directory(tmp_path_factory):
    from cnaas_nms.app_settings import app_settings

    settings_dir = tmp_path_factory.mktemp("settings")
    app_settings.SETTINGS_LOCAL = settings_dir
    print(f"placing settings in {settings_dir}")
    Repo.clone_from(app_settings.SETTINGS_REMOTE, app_settings.SETTINGS_LOCAL)
    return settings_dir


@pytest.fixture(scope="session")
def redis(session_scoped_container_getter):
    """Ensures Redis server is running and available"""
    # This uses pytest-docker-compose, but could also just use pytest-docker for fewer moving parts
    assert wait_for_port('127.0.0.1', 6379), "Could not connect to Redis"
    yield True

@pytest.fixture(scope="session")
def postgresql(session_scoped_container_getter):
    """Ensures PostgreSQL server is running and available"""
    # This uses pytest-docker-compose, but could also just use pytest-docker for fewer moving parts
    # It could also just use pytest-postgresql (which has options to load specific SQL fixtures as
    # well)
    assert wait_for_port('127.0.0.1', 5432), "Could not connect to PostgreSQL"
    yield True


def wait_for_port(host: str, port: int, tries=10) -> bool:
    """Waits for TCP port to receive connections"""
    for retry in range(tries):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            if sock.connect_ex((host, port)) == 0:
                print(f"{host}:{port} responded")
                time.sleep(1)  # port open != service ready, so wait slightly longer
                return True
        time.sleep(0.5)
    print(f"NO RESPONSE from {host}:{port}")
    return False

