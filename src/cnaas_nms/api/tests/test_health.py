import unittest
from unittest.mock import patch

import pytest

from cnaas_nms.api import health

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def uncached_readiness(monkeypatch):
    """Report the current state of the dependencies, so a cached result cannot answer for the next test."""
    monkeypatch.setattr(health, "_readiness_cache", None)
    monkeypatch.setattr(health, "READINESS_CACHE_SECONDS", 0)


def checks_by_name(result):
    return {check["name"]: check["status"] for check in result.json["checks"]}


def test_live_reports_up(client):
    result = client.get("/api/health/live")

    assert result.status_code == 200
    assert result.json["status"] == "UP"


def test_live_reports_up_while_dependencies_are_down(client):
    with (
        patch("cnaas_nms.api.health.sqla_session", side_effect=Exception("Postgres down")),
        patch("cnaas_nms.api.health.redis_session", side_effect=Exception("Redis down")),
    ):
        result = client.get("/api/health/live")

    # The process is alive and should not be restarted over an outage it cannot fix
    assert result.status_code == 200
    assert result.json["status"] == "UP"


def test_ready_reports_up(client):
    result = client.get("/api/health/ready")

    assert result.status_code == 200
    assert result.json["status"] == "UP"
    assert checks_by_name(result) == {"postgres": "UP", "redis": "UP"}


def test_ready_reports_down_when_postgres_is_down(client):
    with patch("cnaas_nms.api.health.sqla_session", side_effect=Exception("Postgres down")):
        result = client.get("/api/health/ready")

    assert result.status_code == 503
    assert result.json["status"] == "DOWN"
    assert checks_by_name(result) == {"postgres": "DOWN", "redis": "UP"}


def test_ready_reports_down_when_redis_is_down(client):
    with patch("cnaas_nms.api.health.redis_session", side_effect=Exception("Redis down")):
        result = client.get("/api/health/ready")

    assert result.status_code == 503
    assert result.json["status"] == "DOWN"
    assert checks_by_name(result) == {"postgres": "UP", "redis": "DOWN"}


def test_ready_recovers_when_postgres_returns(client):
    with patch("cnaas_nms.api.health.sqla_session", side_effect=Exception("Postgres down")):
        client.get("/api/health/ready")

    result = client.get("/api/health/ready")

    assert result.status_code == 200
    assert result.json["status"] == "UP"


def test_health_reports_the_dependencies(client):
    result = client.get("/api/health")

    assert result.status_code == 200
    assert result.json["status"] == "UP"
    assert checks_by_name(result) == {"postgres": "UP", "redis": "UP"}


def test_health_reports_down_when_a_dependency_is_down(client):
    with patch("cnaas_nms.api.health.redis_session", side_effect=Exception("Redis down")):
        result = client.get("/api/health")

    assert result.status_code == 503
    assert result.json["status"] == "DOWN"


def test_ready_reuses_a_result_within_the_cache_interval(client, monkeypatch):
    monkeypatch.setattr(health, "READINESS_CACHE_SECONDS", 60)
    client.get("/api/health/ready")

    # A dependency that drops out is not reported until the cached result expires
    with patch("cnaas_nms.api.health.redis_session", side_effect=Exception("Redis down")):
        result = client.get("/api/health/ready")

    assert result.status_code == 200
    assert result.json["status"] == "UP"


if __name__ == "__main__":
    unittest.main()
