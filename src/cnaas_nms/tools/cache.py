import json
import time
from typing import Optional

from redis.exceptions import RedisError

from cnaas_nms.db.session import redis_session
from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.oidc.token import Token

logger = get_logger()


REDIS_OAUTH_TOKEN_INFO_KEY = "oauth_userinfo"


def get_token_info_from_cache(token: Token) -> Optional[dict]:
    """Check if the userinfo is in the cache to avoid multiple calls to the OIDC server"""
    try:
        with redis_session() as redis:
            cached_token_info = redis.hget(REDIS_OAUTH_TOKEN_INFO_KEY, token.decoded_token["sub"])
            if cached_token_info:
                return json.loads(cached_token_info)
    except RedisError as e:
        logger.debug("Redis cache error: {}".format(str(e)))
    except (TypeError, KeyError) as e:
        logger.debug("Error while getting userinfo cache: {}".format(str(e)))
    return None


def put_token_info_in_cache(token: Token, token_info) -> bool:
    """Put the userinfo in the cache to avoid multiple calls to the OIDC server"""
    try:
        with redis_session() as redis:
            if "exp" in token.decoded_token:
                redis.hsetnx(REDIS_OAUTH_TOKEN_INFO_KEY, token.decoded_token["sub"], token_info)
                # expire hash at access_token expiry time or 1 hour from now (whichever is sooner)
                # Entire hash is expired, since redis does not support expiry on individual keys
                expire_at = min(int(token.decoded_token["exp"]), int(time.time()) + 3600)
                redis.expireat(REDIS_OAUTH_TOKEN_INFO_KEY, when=expire_at, lt=True)
                return True
    except RedisError as e:
        logger.debug("Redis cache error: {}".format(str(e)))
    except (TypeError, KeyError) as e:
        logger.debug("Error while getting userinfo cache: {}".format(str(e)))
    return False
