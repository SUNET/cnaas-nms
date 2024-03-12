from authlib.integrations.flask_oauth2 import ResourceProtector, current_token
from authlib.oauth2.rfc6749.requests import OAuth2Request
from authlib.oauth2.rfc6750 import BearerTokenValidator
from flask_jwt_extended import get_jwt_identity as get_jwt_identity_orig
from flask_jwt_extended import jwt_required as jwt_orig
from jose import exceptions, jwt
from jwt.exceptions import ExpiredSignatureError, InvalidKeyError, InvalidTokenError

from cnaas_nms.app_settings import api_settings, auth_settings
from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.oidc.key_management import get_key
from cnaas_nms.tools.oidc.oidc_client_call import get_oauth_token_info
from cnaas_nms.tools.oidc.token import Token
from cnaas_nms.tools.rbac.rbac import check_if_api_call_is_permitted, get_permissions_user

logger = get_logger()


def jwt_required(fn):
    """This function enables development without Oauth."""
    if api_settings.JWT_ENABLED:
        return jwt_orig()(fn)
    else:
        return fn


def get_jwt_identity():
    """This function overides the identity when needed."""
    return get_jwt_identity_orig() if api_settings.JWT_ENABLED else "admin"


class MyBearerTokenValidator(BearerTokenValidator):
    def authenticate_token(self, token_string: str) -> Token:
        """Check if token is active.

        If JWT is disabled, we return because no token is needed.

        We decode the header and check if it's good. If not,
        we check if we can validate the user using the userinfo endpoint.

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
            # check if we can still authenticate the user with user info
            token = Token(token_string, None)
            get_oauth_token_info(token)
            return token

        # get the key
        key = get_key(unverified_header.get("kid"))

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
            # make an token object to make it easier to validate
            token = Token(token_string, decoded_token)
            return token
        except exceptions.ExpiredSignatureError as e:
            raise ExpiredSignatureError(e)
        except exceptions.JWKError as e:
            logger.error("Invalid Key")
            raise InvalidKeyError(e)
        except exceptions.JWTError as e:
            logger.error("Invalid Token")
            raise InvalidTokenError(e)

    def validate_token(self, token, scopes, request: OAuth2Request) -> Token:
        """Check if token matches the requested scopes and user has permission to execute the API call."""
        if auth_settings.PERMISSIONS_DISABLED:
            return token
        #  For api call that everyone is always allowed to do
        if scopes is not None and "always_permitted" in scopes:
            return token
        permissions_rules = auth_settings.PERMISSIONS
        if not permissions_rules:
            logger.warning("No permissions defined, so nobody is permitted to do any api calls.")
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
