
from authlib.integrations.flask_oauth2 import ResourceProtector, current_token
from authlib.oauth2.rfc6750 import errors, BearerTokenValidator
from jose import jwt
from jose import exceptions
from jwt.exceptions import InvalidTokenError, InvalidKeyError, ExpiredSignatureError
import requests
from typing import Mapping, Any

from cnaas_nms.tools.log import get_logger
from cnaas_nms.app_settings import auth_settings, api_settings


logger = get_logger()
oauth_required = ResourceProtector()


class MyBearerTokenValidator(BearerTokenValidator):
    keys: Mapping[str, Any] = {}

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
        # If JWT is disabled, no token is needed
        if not api_settings.JWT_ENABLED:
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
                logger.info('JWT.decode didnt work. Get the keys and retry.')
                response = requests.get(url=auth_settings.OIDC_CONF_WELL_KNOWN_URL.split('.well-known')[0] + 'oidc/certs')
                self.keys = response.json()["keys"]
                # decode the token again
                decoded_token = jwt.decode(token_string, self.keys, algorithms=algorithm, audience=auth_settings.OIDC_CLIENT_ID)
            except exceptions.ExpiredSignatureError as e:
                raise ExpiredSignatureError(e)
            except exceptions.JWKError as e:
                logger.error("Invalid Key")
                raise InvalidKeyError(e)
        
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
        # if self.scope_insufficient(token.get('scope'), scopes):
        #     raise errors.InsufficientScopeError()
        return token


oauth_required.register_token_validator(MyBearerTokenValidator())


def get_oauth_identity():
    """Give back the email address of the OAUTH account

        If JWT is disabled, we return "admin".

        We do an api call to request userinfo. This gives back all the userinfo.
        We get the right info from there and return this to the user.

        Returns:
            email(str): Email of the logged in user

    """
    # if jwt disabled, return admin
    if not api_settings.JWT_ENABLED:
        return "admin"

    # apicall to get userinfo
    url = auth_settings.OIDC_CONF_WELL_KNOWN_URL.split('.well-known')[0] + 'oidc/userinfo'
    data = {'token_type_hint': 'access_token'}
    headers = {"Authorization": "Bearer " + current_token["access_token"]}
    try:
        resp = requests.post(url, data=data, headers=headers)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise errors.InvalidTokenError(e)
    # TODO check what we want to return, name or email?
    return resp.json()["email"]
