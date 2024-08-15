import json
from typing import Optional

import requests
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from requests.auth import HTTPBasicAuth

from cnaas_nms.app_settings import auth_settings
from cnaas_nms.tools.cache import get_token_info_from_cache, put_token_info_in_cache
from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.oidc.token import Token

logger = get_logger()


def get_openid_configuration(session: requests.Session) -> dict:
    """Get the openid configuration"""
    try:
        request_openid_configuration = session.get(auth_settings.OIDC_CONF_WELL_KNOWN_URL)
        request_openid_configuration.raise_for_status()
        openid_configuration = request_openid_configuration.json()
        return openid_configuration
    except requests.exceptions.HTTPError:
        raise ConnectionError("Can't reach the OIDC URL")
    except requests.exceptions.ConnectionError:
        raise ConnectionError("OIDC metadata unavailable")
    except requests.exceptions.JSONDecodeError as e:
        raise InvalidTokenError("Invalid JSON in openid Config response: {}".format(str(e)))


def get_token_info_from_userinfo(session: requests.Session, token: Token, user_info_endpoint: str) -> str:
    """Get token info from userinfo"""
    try:
        userinfo_data = {"token_type_hint": "access_token"}
        userinfo_headers = {"Authorization": "Bearer " + token.token_string}
        userinfo_resp = session.post(user_info_endpoint, data=userinfo_data, headers=userinfo_headers)
        userinfo_resp.raise_for_status()
        userinfo_resp.json()
        token_info = userinfo_resp.text
        return token_info
    except requests.exceptions.HTTPError as e:
        try:
            body = json.loads(e.response.content)
            logger.debug("OIDC userinfo endpoint request not successful: " + body["error_description"])
            raise e
        except (json.decoder.JSONDecodeError, KeyError):
            logger.debug("OIDC userinfo endpoint request not successful: {}".format(str(e)))
            raise e
    except requests.exceptions.JSONDecodeError as e:
        raise InvalidTokenError("Invalid JSON in userinfo response: {}".format(str(e)))


def get_token_info_from_introspect(session: requests.Session, token: Token, introspection_endpoint: str) -> str:
    """Get token info from introspect"""
    try:
        introspect_data = {"token": token.token_string}
        introspect_auth = HTTPBasicAuth(auth_settings.OIDC_CLIENT_ID, auth_settings.OIDC_CLIENT_SECRET)
        introspect_resp = session.post(introspection_endpoint, data=introspect_data, auth=introspect_auth)
        introspect_resp.raise_for_status()
        introspect_json = introspect_resp.json()
        if "active" in introspect_json and introspect_json["active"]:
            token_info = introspect_resp.text
            return token_info
        else:
            raise ExpiredSignatureError("Token is no longer active")

    except requests.exceptions.HTTPError as e:
        try:
            body = json.loads(e.response.content)
            logger.debug("OIDC introspection endpoint request not successful: " + body["error_description"])
            raise InvalidTokenError(body["error_description"])
        except (json.decoder.JSONDecodeError, KeyError):
            logger.debug("OIDC introspection endpoint request not successful: {}".format(str(e)))
            raise InvalidTokenError(str(e))
    except requests.exceptions.JSONDecodeError as e:
        raise InvalidTokenError("Invalid JSON in introspection response: {}".format(str(e)))


def get_oauth_token_info(token: Token) -> Optional[dict]:
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

    # Get the cached token info

    cached_token_info = get_token_info_from_cache(token)
    if cached_token_info:
        return cached_token_info

    # Get the openid-configuration
    session = requests.Session()
    openid_configuration = get_openid_configuration(session)

    # Request the userinfo
    try:
        token_info = get_token_info_from_userinfo(session, token, openid_configuration["userinfo_endpoint"])
    except requests.exceptions.HTTPError as e:
        # if the userinfo doesn't work, try the introspectinfo
        introspect_endpoint = openid_configuration.get(
            "introspection_endpoint", openid_configuration.get("introspect_endpoint", None)
        )
        if introspect_endpoint:
            token_info = get_token_info_from_introspect(session, token, introspect_endpoint)
        else:
            raise e

    except requests.exceptions.JSONDecodeError as e:
        raise InvalidTokenError("Invalid JSON in userinfo response: {}".format(str(e)))

    # put the token info in cache
    put_token_info_in_cache(token, token_info)
    return json.loads(token_info)
