from typing import Literal

from flask import Blueprint, jsonify
from sqlalchemy import text

from cnaas_nms.db.session import redis_session, sqla_session
from cnaas_nms.tools.log import get_logger

logger = get_logger()

health_bp = Blueprint("health", __name__, url_prefix="/api")


@health_bp.get("/health")
def get_health():
    postgres_status: Literal["healthy", "unhealthy"]
    redis_status: Literal["healthy", "unhealthy"]

    # Fetch postgresql health status
    try:
        with sqla_session() as session:  # type: ignore
            session.execute(text("SELECT 1"))
            postgres_status = "healthy"
    except Exception as e:
        logger.error("Postgres health check failed", exc_info=e)
        postgres_status = "unhealthy"

    # Fetch redis health status
    try:
        with redis_session() as redis:  # type: ignore
            redis.ping()
            redis_status = "healthy"
    except Exception as e:
        logger.error("Redis health check failed", exc_info=e)
        redis_status = "unhealthy"

    if postgres_status == "healthy" and redis_status == "healthy":
        return jsonify(
            {
                "status": "success",
                "data": {
                    "checks": {
                        "postgres": postgres_status,
                        "redis": redis_status,
                    }
                },
            }
        ), 200

    return jsonify(
        {
            "status": "error",
            "data": {
                "checks": {
                    "postgres": postgres_status,
                    "redis": redis_status,
                }
            },
        }
    ), 503
