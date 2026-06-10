import json
from typing import List

from redis.exceptions import RedisError

from cnaas_nms.db.session import redis_session
from cnaas_nms.tools.log import get_logger

REDIS_FENCING_TOKENS_KEY = "syncto_fencing_tokens"
FENCING_TOKEN_TTL = 7200  # 2 hours in seconds

logger = get_logger()


class FencingError(Exception):
    pass


def create_syncto_fencing_token(job_id: int, device_list: List[str]):
    """Save a fencing token (job_id) with its device list to Redis after a successful dry run.

    The token is stored in a Redis HASH where the field is the job_id and the
    value is the JSON-encoded device list. The entire HASH has a TTL of 2 hours
    as a safety net to prevent tokens from being valid indefinitely.
    """
    try:
        with redis_session() as redis:  # type: ignore
            redis.hset(REDIS_FENCING_TOKENS_KEY, str(job_id), json.dumps(device_list))
            redis.expire(REDIS_FENCING_TOKENS_KEY, FENCING_TOKEN_TTL)
            print_device_list = ", ".join(device_list[:10]) + (
                f"... ({len(device_list)} total)" if len(device_list) > 10 else ""
            )
            logger.debug("Created fencing token for job_id {} with devices: {}".format(job_id, print_device_list))
    except RedisError as e:
        logger.exception("Redis Error while creating fencing token: {}".format(e))
        raise


def get_fencing_token(job_id: int) -> bool:
    """Check if a fencing token (job_id) is still valid.

    Returns True if the token exists in the Redis HASH, False otherwise.
    """
    try:
        with redis_session() as redis:  # type: ignore
            return redis.hexists(REDIS_FENCING_TOKENS_KEY, str(job_id))
    except RedisError as e:
        logger.exception("Redis Error while checking fencing token: {}".format(e))
        raise


def delete_fencing_token(hostname: str):
    """Delete fencing tokens whose device list contains the given hostname.

    Called when a sync event occurs for a specific host, invalidating only
    tokens that targeted that host.
    """
    try:
        with redis_session() as redis:  # type: ignore
            all_tokens = redis.hgetall(REDIS_FENCING_TOKENS_KEY)
            for token_job_id, device_list_json in all_tokens.items():
                device_list = json.loads(device_list_json)
                if hostname in device_list:
                    redis.hdel(REDIS_FENCING_TOKENS_KEY, token_job_id)
                    logger.debug(
                        "Deleted fencing token {} because hostname {} is in device list".format(token_job_id, hostname)
                    )
    except RedisError as e:
        logger.exception("Redis Error while deleting fencing token for hostname {}: {}".format(hostname, e))


def delete_all_fencing_tokens():
    """Delete all fencing tokens from Redis.

    Invalidates all outstanding tokens regardless of their device lists.
    """
    try:
        with redis_session() as redis:  # type: ignore
            result = redis.delete(REDIS_FENCING_TOKENS_KEY)
            if result:
                logger.debug("Deleted all fencing tokens from Redis")
    except RedisError as e:
        logger.exception("Redis Error while deleting fencing tokens: {}".format(e))
