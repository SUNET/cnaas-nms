import time
import socket
import os
from contextlib import closing

from git import Repo

import pytest


def pytest_configure(config):
    # Disable JWT tokens during unit testing (since app defaults want to load from global paths)
    from cnaas_nms.app_settings import api_settings, app_settings
    api_settings.JWT_ENABLED = False

    app_settings.TEMPLATES_REMOTE = "git://gitops.sunet.se/cnaas-lab-templates"
    app_settings.SETTINGS_REMOTE = "git://gitops.sunet.se/cnaas-lab-settings"


@pytest.fixture(scope="session")
def settings_directory(tmp_path_factory):
    from cnaas_nms.app_settings import app_settings

    if os.getenv('PYTEST_SETTINGS_CLONED', '0').strip() in ('0', 'off', 'false', 'no'):
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

    if os.getenv('PYTEST_TEMPLATES_CLONED', '0').strip() in ('0', 'off', 'false', 'no'):
        templates_dir = tmp_path_factory.mktemp("templates")
        app_settings.TEMPLATES_LOCAL = templates_dir
        print(f"placing settings in {templates_dir}")
        Repo.clone_from(app_settings.TEMPLATES_REMOTE, app_settings.TEMPLATES_LOCAL)
        return templates_dir
    else:
        return app_settings.TEMPLATES_LOCAL


@pytest.fixture(scope="session")
def redis(request):
    """Ensures Redis server is running and available"""
    # This uses pytest-docker-compose, but could also just use pytest-docker for fewer moving parts
    if os.getenv('PYTEST_REDIS_EXTERNAL', '0').strip() in ('0', 'off', 'false', 'no'):
        request.getfixturevalue("session_scoped_container_getter")
        assert wait_for_port('127.0.0.1', 6379), "Could not connect to Redis"
    yield True


@pytest.fixture(scope="session")
def postgresql(request):
    """Ensures PostgreSQL server is running and available"""
    # This uses pytest-docker-compose, but could also just use pytest-docker for fewer moving parts
    # It could also just use pytest-postgresql (which has options to load specific SQL fixtures as
    # well)
    if os.getenv('PYTEST_POSTGRES_EXTERNAL', '0').strip() in ('0', 'off', 'false', 'no'):
        request.getfixturevalue("session_scoped_container_getter")
        assert wait_for_port('127.0.0.1', 5432), "Could not connect to PostgreSQL"
    # There is an apparent lag between the server responding to TCP port 5432 and actually being
    # ready to serve database connections. Sleeping for 1 second is the naive solution here,
    # but it's okay, since it only happens the first time the fixture is used in a test session.
    # A more complete solution would check that we can actually establish a PostgreSQL client
    # connection.
    time.sleep(5)
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

