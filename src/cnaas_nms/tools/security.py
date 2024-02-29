import json
import time
from typing import Any, Mapping, Optional

import requests
from authlib.integrations.flask_oauth2 import ResourceProtector, current_token
from authlib.oauth2.rfc6749.requests import OAuth2Request
from authlib.oauth2.rfc6750 import BearerTokenValidator
from flask_jwt_extended import get_jwt_identity as get_jwt_identity_orig
from flask_jwt_extended import jwt_required as jwt_orig
from jose import exceptions, jwt
from jwt.exceptions import ExpiredSignatureError, InvalidKeyError, InvalidTokenError
from redis.exceptions import RedisError
from requests.auth import HTTPBasicAuth

from cnaas_nms.app_settings import api_settings, auth_settings
from cnaas_nms.db.session import redis_session
from cnaas_nms.scheduler.scheduler import SingletonType
from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.rbac.rbac import check_if_api_call_is_permitted, get_permissions_user
from cnaas_nms.tools.rbac.token import Token

logger = get_logger()


REDIS_OAUTH_USERINFO_KEY = "oauth_userinfo"


class JWKSStore(object, metaclass=SingletonType):
    keys: Mapping[str, Any]

    def __init__(self, keys: Optional[Mapping[str, Any]] = None):
        if keys:
            self.keys = keys
        else:
            self.keys = {}


def jwt_required(fn):
    """
    This function enables development without Oauth.
    """
    if api_settings.JWT_ENABLED:
        return jwt_orig()(fn)
    else:
        return fn


def get_jwt_identity():
    """
    This function overides the identity when needed.
    """
    return get_jwt_identity_orig() if api_settings.JWT_ENABLED else "admin"


def get_oauth_token_info(token: Token) -> Any:
    """Give back the details about the token from userinfo or introspection

    If OIDC is disabled, we return None.

    For authorization code access_tokens we can use userinfo endpoint,
    for client_credentials we can use introspection endpoint.

    Returns:
        resp.json(): Object of the user info or introspection

    """
    # For now unnecessary, useful when we only use one log in method
    if not auth_settings.OIDC_ENABLED:
        return None
    # Check if the userinfo is in the cache to avoid multiple calls to the OIDC server
    try:
        with redis_session() as redis:
            cached_userinfo = redis.hget(REDIS_OAUTH_USERINFO_KEY, token.decoded_token["sub"])
            if cached_userinfo:
                return json.loads(cached_userinfo)
    except RedisError as e:
        logger.debug("Redis cache error: {}".format(str(e)))
    except (TypeError, KeyError) as e:
        logger.debug("Error while getting userinfo cache: {}".format(str(e)))

    # Request the userinfo
    try:
        s = requests.Session()
        metadata = s.get(auth_settings.OIDC_CONF_WELL_KNOWN_URL)
        metadata.raise_for_status()
    except requests.exceptions.HTTPError:
        raise ConnectionError("Can't reach the OIDC URL")
    except requests.exceptions.ConnectionError:
        raise ConnectionError("OIDC metadata unavailable")
    user_info_endpoint = metadata.json()["userinfo_endpoint"]
    introspection_endpoint = metadata.json()["introspection_endpoint"]
    userinfo_data = {"token_type_hint": "access_token"}
    userinfo_headers = {"Authorization": "Bearer " + token.token_string}
    introspect_data = {"token": token.token_string}
    introspect_auth = HTTPBasicAuth(auth_settings.OIDC_CLIENT_ID, auth_settings.OIDC_CLIENT_SECRET)
    token_info: str = ""

    try:
        userinfo_resp = s.post(user_info_endpoint, data=userinfo_data, headers=userinfo_headers)
        if userinfo_resp.status_code in [401, 403, 404]:
            introspect_resp = s.post(introspection_endpoint, data=introspect_data, auth=introspect_auth)
            introspect_resp.raise_for_status()
            introspect_json = introspect_resp.json()
            if "active" in introspect_json and introspect_json["active"]:
                token_info = introspect_resp.text
            else:
                raise InvalidTokenError("Token is no longer active")
        else:
            userinfo_resp.raise_for_status()
            userinfo_resp.json()
            token_info = userinfo_resp.text

        with redis_session() as redis:
            if "exp" in token.decoded_token:
                redis.hsetnx(REDIS_OAUTH_USERINFO_KEY, token.decoded_token["sub"], token_info)
                # expire hash at access_token expiry time or 1 hour from now
                # (whichever is sooner)
                # Entire hash is expired, since redis does not support expiry on individual keys
                expire_at = min(int(token.decoded_token["exp"]), int(time.time()) + 3600)
                redis.expireat(REDIS_OAUTH_USERINFO_KEY, when=expire_at, lt=True)
    except requests.exceptions.HTTPError as e:
        try:
            body = json.loads(e.response.content)
            logger.debug("OIDC userinfo endpoint request not successful: " + body["error_description"])
            raise InvalidTokenError(body["error_description"])
        except (json.decoder.JSONDecodeError, KeyError):
            logger.debug("OIDC userinfo endpoint request not successful: {}".format(str(e)))
            raise InvalidTokenError(str(e))
    except requests.exceptions.JSONDecodeError as e:
        raise InvalidTokenError("Invalid JSON in userinfo/introspection response: {}".format(str(e)))
    except RedisError as e:
        logger.debug("Redis cache error: {}".format(str(e)))
    except (TypeError, KeyError) as e:
        logger.debug("Error while getting userinfo cache: {}".format(str(e)))
    return json.loads(token_info)


class MyBearerTokenValidator(BearerTokenValidator):
    def get_keys(self):
        """Get the keys for the OIDC decoding"""
        try:
            s = requests.Session()
            metadata = s.get(auth_settings.OIDC_CONF_WELL_KNOWN_URL)
            keys_endpoint = metadata.json()["jwks_uri"]
            response = s.get(url=keys_endpoint)
            jwks_store = JWKSStore()
            jwks_store.keys = response.json()["keys"]
        except KeyError as e:
            raise InvalidKeyError(e)
        except requests.exceptions.HTTPError as e:
            raise InvalidKeyError(e)

    def get_key(self, kid):
        """Get the key based on the kid"""
        jwks_store = JWKSStore()
        key = [k for k in jwks_store.keys if k["kid"] == kid]
        if len(key) == 0:
            logger.debug("Key not found. Get the keys.")
            self.get_keys()
            if len(jwks_store.keys) == 0:
                logger.error("Keys not downloaded")
                raise InvalidKeyError()
            try:
                key = [k for k in jwks_store.keys if k["kid"] == kid]
            except KeyError as e:
                logger.error("Keys in different format?")
                raise InvalidKeyError(e)
            if len(key) == 0:
                logger.error("Key not in keys")
                raise InvalidKeyError()
        return key

    def authenticate_token(self, token_string: str):
        """Check if token is active.

        If JWT is disabled, we return because no token is needed.

        We decode the header and check if it's good.

        We decode the token using the keys.
        We first check if we can decode it, if not we request the keys.
        The decode function also checks if it's not expired.
        We get de decoded _token back, but for now we do nothing with this.

        Input
            token_string(str): The tokenstring
        Returns:
            token(dict): Dictionary with access_token, decoded_token, token_type, audience, expires_at

        """
        # If OIDC is disabled, no token is needed (for future use)
        if not auth_settings.OIDC_ENABLED:
            return "no-token-needed"

        # First decode the header
        try:
            unverified_header = jwt.get_unverified_header(token_string)
        except exceptions.JWSError as e:
            raise InvalidTokenError(e)
        except exceptions.JWTError:
            # check if we can still get the user info
            token = Token(token_string, None)
            get_oauth_token_info(token)

            return token

        # get the key
        key = self.get_key(unverified_header.get("kid"))

        # decode the token
        algorithm = unverified_header.get("alg")
        try:
            decoded_token = jwt.decode(
                token_string,
                key,
                algorithms=algorithm,
                audience=auth_settings.AUDIENCE,
                options={"verify_aud": auth_settings.VERIFY_AUDIENCE},
            )
        except exceptions.ExpiredSignatureError as e:
            raise ExpiredSignatureError(e)
        except exceptions.JWKError as e:
            logger.error("Invalid Key")
            raise InvalidKeyError(e)
        except exceptions.JWTError as e:
            logger.error("Invalid Token")
            raise InvalidTokenError(e)

        # make an token object to make it easier to validate
        token = Token(token_string, decoded_token)
        return token

    def validate_token(self, token, scopes, request: OAuth2Request):
        """Check if token matches the requested scopes and user has permission to execute the API call."""
        if auth_settings.PERMISSIONS_DISABLED:
            logger.debug("Permissions are disabled. Everyone can do every api call")
            return token
        #  For api call that everyone is always allowed to do
        if scopes is not None and "always_permitted" in scopes:
            return token
        permissions_rules = auth_settings.PERMISSIONS
        if not permissions_rules:
            logger.debug("No permissions defined, so nobody is permitted to do any api calls.")
            raise PermissionError()
        user_info = get_oauth_token_info(token)
        permissions = get_permissions_user(permissions_rules, user_info)
        if len(permissions) == 0:
            raise PermissionError()
        if check_if_api_call_is_permitted(request, permissions):
            return token
        else:
            raise PermissionError()


def get_oauth_identity() -> str:
    """Give back the username of the OAUTH account

    If JWT is disabled, we return "admin".

    We do an api call to request userinfo. This gives back all the userinfo.
    We get the right info from there and return this to the user.

    Returns:
        username(str): Username of the logged in user

    """
    # For now unnecersary, useful when we only use one log in method
    if not auth_settings.OIDC_ENABLED:
        return "Admin"
    token_info = get_oauth_token_info(current_token)
    if auth_settings.OIDC_USERNAME_ATTRIBUTE in token_info:
        return token_info[auth_settings.OIDC_USERNAME_ATTRIBUTE]
    elif "client_id" in token_info:
        return token_info["client_id"]
    else:
        error_message = "{} or client_id is a required claim for oauth".format(auth_settings.OIDC_USERNAME_ATTRIBUTE)
        logger.error(error_message)
        raise KeyError(error_message)


# check which method we use to log in and load vars needed for that
if auth_settings.OIDC_ENABLED is True:
    oauth_required = ResourceProtector()
    oauth_required.register_token_validator(MyBearerTokenValidator())
    login_required = oauth_required(optional=not auth_settings.OIDC_ENABLED)
    get_identity = get_oauth_identity
    login_required_all_permitted = oauth_required(scopes=["always_permitted"])
else:
    oauth_required = None
    login_required = jwt_required
    get_identity = get_jwt_identity
    login_required_all_permitted = jwt_required
