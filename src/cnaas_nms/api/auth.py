
from flask import url_for, redirect, current_app
from flask_restx import Namespace, Resource

from cnaas_nms.api.generic import empty_result
from cnaas_nms.tools.log import get_logger
from cnaas_nms.version import __api_version__
from cnaas_nms.app_settings import auth_settings

from requests.models import PreparedRequest

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
s
        """
        oauth_client = current_app.extensions["authlib.integrations.flask_client"]
        redirect_uri = url_for('auth_auth_api', _external=True)

        try:
            return oauth_client.connext.authorize_redirect(redirect_uri)
        except Exception as e:
            logger.error("Exception during authorized redirect: {}".format(str(e)))
            return empty_result(status="error", data="Exception during authorized redirect."), 500


class AuthApi(Resource):
    def get(self):
        """Function to authenticate the user.
        This API call is called by the OAUTH login after the user has logged in.
        We get the users token and redirect them to right page.

        Returns:
            A HTTP redirect response to the url in the frontend that handles the repsonse after login.
            The access token is a parameter in the url

        """

        oauth_client = current_app.extensions["authlib.integrations.flask_client"]

        try:
            token = oauth_client.connext.authorize_access_token()
        except Exception as e:
            logger.error("Exception during authorization of the access token: {}".format(str(e)))
            return empty_result(status="error", data="Exception during authorization of the access token."), 500

        url = auth_settings.FE_CALLBACK_URL
        parameters = {'token': token["access_token"]}

        req = PreparedRequest()
        req.prepare_url(url, parameters)

        return redirect(req.url, code=302)


api.add_resource(LoginApi, "/login")
api.add_resource(AuthApi, "/auth")
