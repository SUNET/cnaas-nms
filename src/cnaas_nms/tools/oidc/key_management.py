from typing import Any, Mapping, Optional

import requests
from jwt.exceptions import InvalidKeyError

from cnaas_nms.models.singleton import SingletonType
from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.oidc.oidc_client_call import get_openid_configuration

logger = get_logger()


class JWKSStore(object, metaclass=SingletonType):
    keys: Mapping[str, Any]

    def __init__(self, keys: Optional[Mapping[str, Any]] = None):
        if keys:
            self.keys = keys
        else:
            self.keys = {}


def get_keys():
    """Get the keys for the OIDC decoding"""
    try:
        session = requests.Session()
        openid_configuration = get_openid_configuration(session)
        keys_endpoint = openid_configuration["jwks_uri"]
        response = session.get(url=keys_endpoint)
        jwks_store = JWKSStore()
        jwks_store.keys = response.json()["keys"]
    except KeyError as e:
        raise InvalidKeyError(e)
    except requests.exceptions.HTTPError:
        raise ConnectionError("Can't retrieve keys")


def get_key(kid):
    """Get the key based on the kid"""
    jwks_store = JWKSStore()
    key = [k for k in jwks_store.keys if k["kid"] == kid]
    if len(key) == 0:
        logger.debug("Key not found. Get the keys.")
        get_keys()
        if len(jwks_store.keys) == 0:
            logger.error("Keys not downloaded")
            raise ConnectionError("Can't retrieve keys")
        try:
            key = [k for k in jwks_store.keys if k["kid"] == kid]
        except KeyError as e:
            logger.error("Keys in different format?")
            raise InvalidKeyError(e)
        if len(key) == 0:
            logger.error("Key not in keys")
            raise InvalidKeyError()
    return key
