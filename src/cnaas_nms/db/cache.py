"""Cache handling for settings"""
import functools


import redis
from redis_lru import RedisLRU

from cnaas_nms.db.session import get_dbdata

__redis_lru = None


def lru_cache(func):
    """An LRU cache decorator that will use Redis, if available, otherwise in-process caching is
    used.

    When running a fully integrated system, it is expected that Redis will be used, but when
    running unit tests in isolation, in-process caching will be used.
    """
    cache = _get_redis_cache()
    if not cache:
        cache = functools.lru_cache(maxsize=1024)

    return cache(func)


def _get_redis_cache():
    global __redis_lru
    if not __redis_lru:
        try:
            db_data = get_dbdata()
            redis_client = redis.StrictRedis(
                host=db_data['redis_hostname'],
                port=6379,
                retry_on_timeout=True,
                socket_keepalive=True,
            )
            __redis_lru = RedisLRU(redis_client)
        except (FileNotFoundError, KeyError):
            return
    return __redis_lru
