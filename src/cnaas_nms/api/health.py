import logging
import os
import time
import uuid
from typing import Dict, List, Literal, Optional, Tuple

from flask import Blueprint, Response, jsonify
from sqlalchemy import text

from cnaas_nms.db.session import redis_session, sqla_session
from cnaas_nms.tools.log import get_logger

logger = get_logger()

health_bp = Blueprint("health", __name__, url_prefix="/api")

Status = Literal["UP", "DOWN"]

# A readiness result is reused for this long, so that probing often costs no
# more than probing rarely.
READINESS_CACHE_SECONDS = 5.0

_readiness_cache: Optional[Tuple[float, List[Dict[str, str]]]] = None


def check_postgres() -> Status:
    try:
        with sqla_session() as session:  # type: ignore
            session.execute(text("SELECT 1"))
        return "UP"
    except Exception as e:
        logger.warning("Postgres health check failed: {}".format(e))
        return "DOWN"


def check_redis() -> Status:
    try:
        with redis_session() as redis:  # type: ignore
            redis.ping()
        return "UP"
    except Exception as e:
        logger.warning("Redis health check failed: {}".format(e))
        return "DOWN"


def readiness_checks() -> List[Dict[str, str]]:
    """Check the dependencies the API needs to serve requests, at most once every cache interval."""
    global _readiness_cache

    cached = _readiness_cache
    if cached and time.monotonic() - cached[0] < READINESS_CACHE_SECONDS:
        return cached[1]

    checks: List[Dict[str, str]] = [
        {"name": "postgres", "status": check_postgres()},
        {"name": "redis", "status": check_redis()},
    ]
    _readiness_cache = (time.monotonic(), checks)
    return checks


def health_response(checks: List[Dict[str, str]]) -> Tuple[Response, int]:
    status: Status = "UP" if all(check["status"] == "UP" for check in checks) else "DOWN"
    return jsonify({"status": status, "checks": checks}), 200 if status == "UP" else 503


@health_bp.get("/health")
def get_health():
    """Aggregate of every check, so a single call shows whether the API is both running and usable."""
    return health_response(readiness_checks())


@health_bp.get("/health/live")
def get_health_live():
    """Report that the API process runs. Performs no I/O, so a dependency outage never fails it."""
    # TEMPORARY debug marker to investigate duplicate log lines. Remove once resolved.
    logger.info("DEBUG_MARKER pid={} req_id={}".format(os.getpid(), uuid.uuid4()))
    return health_response([])


@health_bp.get("/health/ready")
def get_health_ready():
    """Report whether the API can reach the dependencies it needs to answer requests."""
    return health_response(readiness_checks())


def _describe_handlers(handlers: List[logging.Handler]) -> List[Dict[str, str]]:
    return [
        {"type": type(h).__name__, "id": hex(id(h)), "level": logging.getLevelName(h.level)} for h in handlers
    ]


# TEMPORARY debug endpoint to investigate duplicate log lines. Remove once resolved.
@health_bp.get("/health/debug/logging")
def get_health_debug_logging():
    """Report the current process's logger/handler state, to debug duplicated log lines."""
    root_logger = logging.getLogger()
    cnaas_logger = logging.getLogger("cnaas-nms")
    return (
        jsonify(
            {
                "pid": os.getpid(),
                "root": {
                    "handlers": _describe_handlers(root_logger.handlers),
                    "level": logging.getLevelName(root_logger.level),
                },
                "cnaas-nms": {
                    "handlers": _describe_handlers(cnaas_logger.handlers),
                    "propagate": cnaas_logger.propagate,
                    "level": logging.getLevelName(cnaas_logger.level),
                },
            }
        ),
        200,
    )
