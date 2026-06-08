from redis.exceptions import RedisError

from cnaas_nms.db.session import redis_session
from cnaas_nms.tools.log import get_logger

REDIS_FENCING_TOKENS_KEY = "syncto_fencing_tokens"
FENCING_TOKEN_TTL = 7200  # 2 hours in seconds

logger = get_logger()


class FencingError(Exception):
    pass


def create_syncto_fencing_token(job_id: int):
    """Save a fencing token (job_id) to Redis after a successful dry run.

    The token is stored in a Redis SET. The entire SET has a TTL of 2 hours
    as a safety net to prevent tokens from being valid indefinitely.
    """
    try:
        with redis_session() as redis:  # type: ignore
            redis.sadd(REDIS_FENCING_TOKENS_KEY, str(job_id))
            redis.expire(REDIS_FENCING_TOKENS_KEY, FENCING_TOKEN_TTL)
            logger.debug("Created fencing token for job_id {}".format(job_id))
    except RedisError as e:
        logger.exception("Redis Error while creating fencing token: {}".format(e))
        raise


def get_fencing_token(job_id: str) -> bool:
    """Check if a fencing token (job_id) is still valid.

    Returns True if the token exists in the Redis SET, False otherwise.
    """
    try:
        with redis_session() as redis:  # type: ignore
            return redis.sismember(REDIS_FENCING_TOKENS_KEY, str(job_id))
    except RedisError as e:
        logger.exception("Redis Error while checking fencing token: {}".format(e))
        raise


def delete_all_fencing_tokens():
    """Delete all fencing tokens from Redis.

    Called when a sync event occurs, invalidating all outstanding tokens
    since the device state may have changed.
    """
    try:
        with redis_session() as redis:  # type: ignore
            result = redis.delete(REDIS_FENCING_TOKENS_KEY)
            if result:
                logger.debug("Deleted all fencing tokens from Redis")
    except RedisError as e:
        logger.exception("Redis Error while deleting fencing tokens: {}".format(e))
