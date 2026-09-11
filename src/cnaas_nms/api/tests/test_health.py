import unittest
from unittest.mock import patch


def test_health(client):
    result = client.get("/api/health")

    # 200 OK
    assert result.status_code == 200


def test_health_postgres_down(client):
    # Simulate PostgreSQL being down
    # Mock sqla_session()
    with patch("cnaas_nms.api.health.sqla_session", side_effect=Exception("Postgres down")):
        result = client.get("/api/health")

    # 503 Service Unavailable
    assert result.status_code == 503


def test_health_redis_down(client):
    # Simulate Redis being down
    # Mock redis_session()
    with patch("cnaas_nms.api.health.redis_session", side_effect=Exception("Redis down")):
        result = client.get("/api/health")

    # 503 Service Unavailable
    assert result.status_code == 503


if __name__ == "__main__":
    unittest.main()
