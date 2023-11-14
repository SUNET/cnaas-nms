from flask_jwt_extended import get_jwt_identity as get_jwt_identity_orig
from flask_jwt_extended import jwt_required as jwt_orig
from authlib.integrations.flask_oauth2 import ResourceProtector, current_token
from authlib.oauth2.rfc6750 import errors, BearerTokenValidator
from authlib.oauth2.rfc6749.wrappers import HttpRequest
from jose import jwt
from jose import exceptions
from jwt.exceptions import InvalidTokenError, InvalidKeyError, ExpiredSignatureError, InvalidAudienceError
from flask_jwt_extended.exceptions import NoAuthorizationError
from authlib.oauth2.rfc6749 import MissingAuthorizationError
import requests
from typing import Mapping, Any, List
import re

from cnaas_nms.tools.log import get_logger
from cnaas_nms.app_settings import auth_settings, api_settings
from cnaas_nms.version import __api_version__
import json

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


class Token():
    token_string: str = ""
    decoded_token = {}
    token_type: str = ""
    audience: str = ""
    expires_at = ""

    def __init__(self, token_string, decoded_token, algorithm):
        self.token_string = token_string
        self.decoded_token = decoded_token
        self.token_type = algorithm
        self.audience = auth_settings.OIDC_CLIENT_ID
        self.expires_at = decoded_token["exp"]
    def get_scope():
        return

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
    

    def load_role_yaml():
        '''Load the file with role permission'''
        # TODO check if we want to load this in once and put it in a different place
        # TODO already give back if stuff is missing fromthis file/formatting is wrong etc
        import yaml
        try:
            with open("roles.yml", "r") as roles_file:
                roles_data = yaml.safe_load(roles_file)
        except FileNotFoundError:
            logger.debug('No Roles file. All roles get * rights. ')
            return None
        return roles_data
    

    def get_user_role_from_dic(roles_data, decoded_token):
        '''Get the API permissions of the user'''
        if 'role_in_jwt_element' not in roles_data['config']:
            if "fallback_role" in roles_data["config"] and  roles_data["config"]["fallback_role"] in roles_data["roles"]:
                    user_role = roles_data["config"]["fallback_role"]
            else:
                #TODO maybe just make the scope the fallback?
                logger.debug('Bad Roles file. All roles get * rights. ')
                return None
        if roles_data['config']['role_in_jwt_element'] not in decoded_token:
            if "fallback_role" in roles_data["config"] and  roles_data["config"]["fallback_role"] in roles_data["roles"]:
                user_role = roles_data["config"]["fallback_role"]
            else:
                logger.debug("User doesn't have element :'" + roles_data['config']['role_in_jwt_element'] + "' in JWT token.")
                raise InvalidAudienceError()
        
        # select the right role
        if 'roles_seperated_by' not in roles_data['config'] or roles_data['config']['roles_seperated_by'] == "":
            user_role = decoded_token[roles_data['config']['role_in_jwt_element']]
            user_roles = [user_role]
        else:
            user_roles = decoded_token[roles_data['config']['role_in_jwt_element']].split(roles_data['config']['roles_seperated_by'])
            user_role = None
            for role in user_roles:
                if role in roles_data["roles"]:
                    user_role = role
        if user_role not in roles_data["roles"]:
            if "any" in roles_data["roles"]:
                    user_role = "any"
            else:
                logger.debug('Requested roles: [' + ','.join(user_roles) + ']. Roles not found in roles.yaml. ')
                raise InvalidAudienceError()
        
        # get the permissions of the role
        allowed_api_methods: List[str] = roles_data["roles"][user_role]['allowed_api_methods']
        allowed_api_calls: List[str] = roles_data["roles"][user_role]['allowed_api_calls']

        return allowed_api_methods, allowed_api_calls
    

    def check_if_allowed_to_make_api_call(request: HttpRequest, allowed_api_methods: List[str], allowed_api_calls: List[str]):
        '''Checks if the user has permission to execute the API call'''
        if "*" not in allowed_api_methods and request.method not in allowed_api_methods:
            raise InvalidAudienceError()
        
        prefix = "/api/{}".format(__api_version__)
        short_uri = request.uri[:-1].strip().removeprefix(prefix)
        # added the regex so it's easier to add a bunch of api calls (like all device api calls)
        combined = "(" + ")|(".join(allowed_api_calls) + ")"
         # check if you're permitted to make api call based on uri
        if "*" not in allowed_api_calls and short_uri not in allowed_api_calls and not re.fullmatch(combined, short_uri):
            raise InvalidAudienceError()
        # return the token
        return True 
    

    def validate_token(self, token, scopes, request: HttpRequest):
        """Check if token matches the requested scopes and user has permission to execute the API call."""
        roles_data = self.load_role_yaml()
        if roles_data is None:
            logger.debug('No Roles file. All roles get * rights. ')
            return token
        allowed_api_methods, allowed_api_calls = self.get_user_role_from_dic(roles_data, token["decoded_token"])
        if(self.check_if_allowed_to_make_api_call(request, allowed_api_methods, allowed_api_calls)):
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
