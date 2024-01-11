from typing import Any, Mapping

import requests
from authlib.integrations.flask_oauth2 import ResourceProtector, current_token
from authlib.oauth2.rfc6750 import BearerTokenValidator, errors
from authlib.oauth2.rfc6749.wrappers import HttpRequest
from flask_jwt_extended import get_jwt_identity as get_jwt_identity_orig
from flask_jwt_extended import jwt_required as jwt_orig
from jose import exceptions, jwt
from jwt.exceptions import InvalidTokenError, InvalidKeyError, ExpiredSignatureError, InvalidAudienceError
from cnaas_nms.tools.rbac.rbac import get_permissions_user, check_if_api_call_is_permitted
from cnaas_nms.tools.rbac.token import Token
from cnaas_nms.app_settings import api_settings, auth_settings
from cnaas_nms.tools.log import get_logger

logger = get_logger()


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



def get_oauth_userinfo(token: Token) -> Any:
    """Give back the user info of the OAUTH account

        If OIDC is disabled, we return None.

        We do an api call to request userinfo. This gives back all the userinfo.

        Returns:
            resp.json(): Object of the user info 

    """
    if not auth_settings.OIDC_ENABLED:
        return None
    # Request the userinfo
    metadata = requests.get(auth_settings.OIDC_CONF_WELL_KNOWN_URL)
    user_info_endpoint = metadata.json()["userinfo_endpoint"]
    data = {'token_type_hint': 'access_token'}
    headers = {"Authorization": "Bearer " + token.token_string}
    try:
        resp = requests.post(user_info_endpoint, data=data, headers=headers)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise errors.InvalidTokenError(e)
    return resp.json()

class MyBearerTokenValidator(BearerTokenValidator):
    keys: Mapping[str, Any] = {}

    def get_keys(self):
        """Get the keys for the OIDC decoding"""
        try:
            metadata = requests.get(auth_settings.OIDC_CONF_WELL_KNOWN_URL)
            keys_endpoint = metadata.json()["jwks_uri"]
            response = requests.get(url=keys_endpoint)
            self.keys = response.json()["keys"]
        except KeyError as e: 
            raise InvalidKeyError(e)
        except requests.exceptions.HTTPError as e:
            raise InvalidKeyError(e)

    
    def get_key(self, kid):
        """Get the key based on the kid"""
        key = [k for k in self.keys if k['kid'] == kid]
        if len(key) == 0:
            logger.debug("Key not found. Get the keys.")
            self.get_keys()
            if len(self.keys) == 0:
                logger.error("Keys not downloaded")
                raise InvalidKeyError()
            try:
                key = [k for k in self.keys if k['kid'] == kid]
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
        except exceptions.JWTError as e:
            # check if we can still get the user info
            get_oauth_userinfo(token_string)
            token = {
                "access_token": token_string
            }
            return token

        # get the key
        key = self.get_key(unverified_header.get("kid"))

        # decode the token
        algorithm = unverified_header.get("alg")
        try:
            decoded_token = jwt.decode(
                token_string, key, algorithms=algorithm, audience=auth_settings.OIDC_CLIENT_ID
            )
        except exceptions.ExpiredSignatureError as e:
            raise ExpiredSignatureError(e)
        except exceptions.JWKError:
            logger.error("Invalid Key")
            raise InvalidKeyError(e)
        except exceptions.JWTError as e:
            logger.error("Invalid Token")
            raise InvalidTokenError(e)

        # make an token object to make it easier to validate
        token = Token(token_string, decoded_token)
        return token

    def validate_token(self, token, scopes, request: HttpRequest):
        """Check if token matches the requested scopes and user has permission to execute the API call."""
        if auth_settings.PERMISSIONS_DISABLED:
            logger.debug("Permissions are disabled. Everyone can do every api call")
            return token
        #  For api call that everyone is always allowed to do
        if scopes is not None and "always_permitted" in scopes:
            return token
        permissions_rules = auth_settings.PERMISSIONS
        if permissions_rules is None or len(permissions_rules) == 0:
            logger.debug('No permissions defined, so nobody is permitted to do any api calls.')
            raise InvalidAudienceError()
        user_info = get_oauth_userinfo(token)
        permissions = get_permissions_user(permissions_rules, user_info)
        if len(permissions) == 0:
            raise InvalidAudienceError()
        if check_if_api_call_is_permitted(request, permissions):
            return token
        else:
            raise InvalidAudienceError()


def get_oauth_identity() -> str:
    """Give back the email address of the OAUTH account

        If JWT is disabled, we return "admin".

        We do an api call to request userinfo. This gives back all the userinfo.
        We get the right info from there and return this to the user.

        Returns:
            email(str): Email of the logged in user

    """
    # For now unnecersary, useful when we only use one log in method
    if not auth_settings.OIDC_ENABLED:
        return "Admin"
    userinfo = get_oauth_userinfo(current_token["access_token"])
    if "email" not in userinfo:
        logger.error("Email is a required claim for oauth")
        raise KeyError("Email is a required claim for oauth")
    return userinfo["email"]



# check which method we use to log in and load vars needed for that
if auth_settings.OIDC_ENABLED is True:
    oauth_required = ResourceProtector()
    oauth_required.register_token_validator(MyBearerTokenValidator())
    login_required = oauth_required(optional=not auth_settings.OIDC_ENABLED)
    get_identity = get_oauth_identity
    login_required_all_permitted = oauth_required(scopes=["always_permitted"])
else:
    login_required = jwt_required
    get_identity = get_jwt_identity
    login_required_all_permitted = jwt_required
    
