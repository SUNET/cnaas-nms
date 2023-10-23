from flask_jwt_extended import get_jwt_identity as get_jwt_identity_orig
from flask_jwt_extended import jwt_required as jwt_orig
from authlib.integrations.flask_oauth2 import ResourceProtector, current_token
from authlib.oauth2.rfc6750 import errors, BearerTokenValidator
from jose import jwt
from jose import exceptions
from jwt.exceptions import InvalidTokenError, InvalidKeyError, ExpiredSignatureError
from flask_jwt_extended.exceptions import NoAuthorizationError
from authlib.oauth2.rfc6749 import MissingAuthorizationError
import requests
from typing import Mapping, Any

from cnaas_nms.tools.log import get_logger
from cnaas_nms.app_settings import auth_settings, api_settings

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


class MyResourceProtector(ResourceProtector):
    def raise_error_response(self, error):
        """ Raises no authorization error when missing authorization"""
        if isinstance(error, MissingAuthorizationError):
            raise NoAuthorizationError(error) 
        raise error


class MyBearerTokenValidator(BearerTokenValidator):
    keys: Mapping[str, Any] = {}
    def get_keys(self):
        """Get the keys for the OIDC decoding"""
        metadata = requests.get(auth_settings.OIDC_CONF_WELL_KNOWN_URL)
        keys_endpoint = metadata.json()["jwks_uri"]
        response = requests.get(url=keys_endpoint)
        self.keys = response.json()["keys"]

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
            raise InvalidTokenError(e)

        # decode the token
        algorithm = unverified_header.get('alg')
        try:
            decoded_token = jwt.decode(token_string, self.keys, algorithms=algorithm, audience=auth_settings.OIDC_CLIENT_ID)
        except exceptions.ExpiredSignatureError as e:
            raise ExpiredSignatureError(e)
        except exceptions.JWKError:
            try:
                # with this exception, we first try to reload the keys
                # there is a new key every 24 hours
                logger.debug('JWT.decode didnt work. Get the keys and retry.')
                self.get_keys()

                # decode the token again
                decoded_token = jwt.decode(token_string, self.keys, algorithms=algorithm, audience=auth_settings.OIDC_CLIENT_ID)
            except exceptions.ExpiredSignatureError as e:
                raise ExpiredSignatureError(e)
            except exceptions.JWKError as e:
                logger.error("Invalid Key")
                raise InvalidKeyError(e)
            except exceptions.JWTError as e:
                logger.error("Invalid Token")
                raise InvalidTokenError(e)
        except exceptions.JWTError as e:
            logger.error("Invalid Token")
            raise InvalidTokenError(e)
        
        # make an token object to make it easier to validate
        token = {
            "access_token": token_string,
            "decoded_token": decoded_token,
            "token_type": algorithm,
            "audience": auth_settings.OIDC_CLIENT_ID,
            "expires_at": decoded_token["exp"]
        }
        return token

    def validate_token(self, token, scopes, request):
        """Check if token matches the requested scopes."""
        # For now we don't have a scope yet
        # When needed, look at implementation example here:
        # https://github.com/lepture/authlib/blob/master/authlib/oauth2/rfc6750/validator.py
        return token


def get_oauth_identity():
    """Give back the email address of the OAUTH account

        If JWT is disabled, we return "admin".

        We do an api call to request userinfo. This gives back all the userinfo.
        We get the right info from there and return this to the user.

        Returns:
            email(str): Email of the logged in user

    """
    # For now unnecersary, useful when we nly use one log in method
    if not auth_settings.OIDC_ENABLED:
        return "Admin"
    # Request the userinfo
    metadata = requests.get(auth_settings.OIDC_CONF_WELL_KNOWN_URL)
    user_info_endpoint = metadata.json()["userinfo_endpoint"]
    data = {'token_type_hint': 'access_token'}
    headers = {"Authorization": "Bearer " + current_token["access_token"]}
    try:
        resp = requests.post(user_info_endpoint, data=data, headers=headers)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise errors.InvalidTokenError(e)
    return resp.json()["email"]


# check which method we use to log in and load vars needed for that
if auth_settings.OIDC_ENABLED is True:
    oauth_required = MyResourceProtector()
    oauth_required.register_token_validator(MyBearerTokenValidator())
    login_required = oauth_required(optional=not auth_settings.OIDC_ENABLED)
    get_identity = get_oauth_identity
else:
    login_required = jwt_required
    get_identity = get_jwt_identity
