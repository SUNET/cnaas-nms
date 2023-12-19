from authlib.integrations.base_client.errors import MismatchingStateError
from authlib.integrations.flask_oauth2 import current_token

from flask import current_app, redirect, url_for
from flask_restx import Namespace, Resource
from requests.models import PreparedRequest

from cnaas_nms.api.generic import empty_result
from cnaas_nms.app_settings import auth_settings
from cnaas_nms.tools.security import login_required, get_identity, login_required_all_permitted, get_oauth_userinfo
from cnaas_nms.tools.rbac.rbac import get_permissions_user
from cnaas_nms.tools.log import get_logger
from cnaas_nms.version import __api_version__

logger = get_logger()
api = Namespace("auth", description="API for handling auth", prefix="/api/{}".format(__api_version__))


class LoginApi(Resource):
    def get(self):
        """Function to initiate a login of the user.
        The user will be sent to the page to login.
        Our client info will also be checked.

        Note:
            We also discussed adding state to this function.
            That way you could be sent to the same page once you logged in.
            We would put the relevant information in a dictionary,
            base64 encode it and sent it around as a parameter.
            For now the application is small and it didn't seem needed.

        Returns:
            A HTTP redirect response to OIDC_CONF_WELL_KNOWN_URL we have defined.
            We give the auth call as a parameter to redirect after login is successfull.

        """
        if not auth_settings.OIDC_ENABLED:
            return empty_result(status="error", data="Can't login when OIDC disabled"), 500
        oauth_client = current_app.extensions["authlib.integrations.flask_client"]
        redirect_uri = url_for("auth_auth_api", _external=True)

        return oauth_client.connext.authorize_redirect(redirect_uri)


class AuthApi(Resource):
    def get(self):
        """Function to authenticate the user.
        This API call is called by the OAUTH login after the user has logged in.
        We get the users token and redirect them to right page in the frontend.

        Returns:
            A HTTP redirect response to the url in the frontend that handles the repsonse after login.
            The access token is a parameter in the url

        """

        oauth_client = current_app.extensions["authlib.integrations.flask_client"]

        try:
            token = oauth_client.connext.authorize_access_token()
        except MismatchingStateError as e:
            logger.error("Exception during authorization of the access token: {}".format(str(e)))
            return (
                empty_result(
                    status="error",
                    data="Exception during authorization of the access token. Please try to login again.",
                ),
                502,
            )

        url = auth_settings.FRONTEND_CALLBACK_URL
        parameters = {"token": token["access_token"]}

        req = PreparedRequest()
        req.prepare_url(url, parameters)
        return redirect(req.url, code=302)


class IdentityApi(Resource):
    @login_required
    def get(self):
        identity = get_identity()
        return identity


class PermissionsAPI(Resource):
    @login_required_all_permitted
    def get(self):
        permissions_rules = auth_settings.PERMISSIONS
        if len(permissions_rules) == 0:
            logger.debug('No permissions defined, so nobody is permitted to do any api calls.')
            return []
        user_info = get_oauth_userinfo(current_token)
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        return permissions_of_user


api.add_resource(LoginApi, "/login")
api.add_resource(AuthApi, "/auth")
api.add_resource(IdentityApi, "/identity")
api.add_resource(PermissionsAPI, "/permissions")
