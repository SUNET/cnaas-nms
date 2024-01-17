import os
import re
import sys

from typing import Optional
from engineio.payload import Payload
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, decode_token
from flask_jwt_extended.exceptions import InvalidHeaderError, NoAuthorizationError
from flask_restx import Api
from flask_socketio import SocketIO, join_room
from jwt import decode
from jwt.exceptions import DecodeError, InvalidSignatureError, InvalidTokenError, ExpiredSignatureError, InvalidKeyError
from authlib.integrations.flask_client import OAuth
from authlib.oauth2.rfc6749 import MissingAuthorizationError


from cnaas_nms.api.device import (
    device_api,
    device_cert_api,
    device_discover_api,
    device_init_api,
    device_initcheck_api,
    device_synchistory_api,
    device_syncto_api,
    device_update_facts_api,
    device_update_interfaces_api,
    devices_api,
)
from cnaas_nms.api.auth import api as auth_api
from cnaas_nms.api.firmware import api as firmware_api
from cnaas_nms.api.groups import api as groups_api
from cnaas_nms.api.interface import api as interfaces_api
from cnaas_nms.api.jobs import job_api, joblock_api, jobs_api
from cnaas_nms.api.json import CNaaSJSONEncoder
from cnaas_nms.api.linknet import linknet_api, linknets_api
from cnaas_nms.api.mgmtdomain import mgmtdomain_api, mgmtdomains_api
from cnaas_nms.api.plugins import api as plugins_api
from cnaas_nms.api.repository import api as repository_api
from cnaas_nms.api.settings import api as settings_api
from cnaas_nms.api.system import api as system_api

from cnaas_nms.app_settings import auth_settings
from cnaas_nms.app_settings import api_settings

from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.security import get_oauth_userinfo
from cnaas_nms.version import __api_version__


logger = get_logger()


authorizations = {
    "apikey": {
        "type": "apiKey",
        "in": "header",
        "name": "Authorization",
        "description": "Type in 'Bearer <your JWT token here' to authenticate.",
    }
}

jwt_query_r = re.compile(r"code=[^ &]+")


class CnaasApi(Api):
    def handle_error(self, e):
        if isinstance(e, DecodeError):
            data = {"status": "error", "message": "Could not decode JWT token"}
        elif isinstance(e, InvalidKeyError):
            data = {"status": "error", "message": "Invalid keys {}".format(e)}
        elif isinstance(e, InvalidTokenError):
            data = {"status": "error", "message": "Invalid authentication header: {}".format(e)}
        elif isinstance(e, InvalidSignatureError):
            data = {"status": "error", "message": "Invalid token signature"}
        elif isinstance(e, IndexError):
            # We might catch IndexErrors which are not caused by JWT,
            # but this is better than nothing.
            data = {"status": "error", "message": "JWT token missing?"}
        elif isinstance(e, NoAuthorizationError):
            data = {"status": "error", "message": "JWT token missing?"}
        elif isinstance(e, InvalidHeaderError):
            data = {"status": "error", "message": "Invalid header, JWT token missing? {}".format(e)}
        elif isinstance(e, ExpiredSignatureError):
            data = {"status": "error", "message": "The JWT token is expired"}
        elif isinstance(e, MissingAuthorizationError):
            data = {"status": "error", "message": "JWT token missing?"}
        elif isinstance(e, ConnectionError):
            data = {"status": "error", "message": "ConnectionError: {}".format(e)}
            return jsonify(data), 500
        else:
            return super(CnaasApi, self).handle_error(e)
        return jsonify(data), 401


app = Flask(__name__)

# To register the OAuth client
oauth = OAuth(app)
client = oauth.register(
    "connext",
    server_metadata_url=auth_settings.OIDC_CONF_WELL_KNOWN_URL,
    client_id=auth_settings.OIDC_CLIENT_ID,
    client_secret=auth_settings.OIDC_CLIENT_SECRET,
    client_kwargs={"scope": auth_settings.OIDC_CLIENT_SCOPE},
    response_type="code",
    response_mode="query",
)

app.config["RESTX_JSON"] = {"cls": CNaaSJSONEncoder}

# TODO: make origins configurable
cors = CORS(
    app,
    resources={r"/api/*": {"origins": "*"}},
    expose_headers=["Content-Type", "Authorization", "X-Total-Count", "Link"],
)
Payload.max_decode_packets = 500
socketio = SocketIO(app, cors_allowed_origins="*")


if api_settings.JWT_ENABLED or auth_settings.OIDC_ENABLED:
    app.config["SECRET_KEY"] = os.urandom(128)
if api_settings.JWT_ENABLED:
    try:
        jwt_pubkey = open(api_settings.JWT_CERT).read()
    except Exception as e:
        print("Could not load public JWT cert from api.yml config: {}".format(e))
        sys.exit(1)

    app.config["JWT_PUBLIC_KEY"] = jwt_pubkey
    app.config["JWT_IDENTITY_CLAIM"] = "sub"
    app.config["JWT_ALGORITHM"] = "ES256"
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False
    app.config["JWT_TOKEN_LOCATION"] = ("headers", "query_string")

    jwt = JWTManager(app)

api = CnaasApi(
    app, prefix="/api/{}".format(__api_version__), authorizations=authorizations, security="apikey", doc="/api/doc/"
)

api.add_namespace(auth_api)
api.add_namespace(device_api)
api.add_namespace(devices_api)
api.add_namespace(device_init_api)
api.add_namespace(device_initcheck_api)
api.add_namespace(device_syncto_api)
api.add_namespace(device_discover_api)
api.add_namespace(device_update_facts_api)
api.add_namespace(device_update_interfaces_api)
api.add_namespace(device_cert_api)
api.add_namespace(device_synchistory_api)
api.add_namespace(linknets_api)
api.add_namespace(linknet_api)
api.add_namespace(firmware_api)
api.add_namespace(interfaces_api)
api.add_namespace(job_api)
api.add_namespace(jobs_api)
api.add_namespace(joblock_api)
api.add_namespace(mgmtdomain_api)
api.add_namespace(mgmtdomains_api)
api.add_namespace(groups_api)
api.add_namespace(repository_api)
api.add_namespace(settings_api)
api.add_namespace(plugins_api)
api.add_namespace(system_api)

# SocketIO on connect
@socketio.on("connect")
def socketio_on_connect():
    # get te token string
    token_string = request.args.get('jwt')
    if not token_string:
        return False
    #if oidc, get userinfo
    if auth_settings.OIDC_ENABLED:
        try:
            user = get_oauth_userinfo(token_string)['email']
        except InvalidTokenError as e:
            logger.debug('InvalidTokenError: ' + format(e))
            return False
    # else decode the token and get the sub there
    else:
        try:
            user = decode(token_string, app.config["JWT_PUBLIC_KEY"], algorithms=[app.config["JWT_ALGORITHM"]])['sub']
        except DecodeError as e:
            logger.debug('DecodeError: ' + format(e))
            return False

    if user:
        logger.info("User: {} connected via socketio".format(user))
        return True
    else:
        return False


# SocketIO join event rooms
@socketio.on("events")
def socketio_on_events(data):
    room: Optional[str] = None
    if "loglevel" in data and data["loglevel"] in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        room = data["loglevel"]
    elif "update" in data and data["update"] in ["device", "job"]:
        room = "update_{}".format(data["update"])
    elif "sync" in data and data["sync"] == "all":
        room = "sync"
    else:
        return False  # TODO: how to send error message to client?

    join_room(room)


# Log all requests, include username etc
@app.after_request
def log_request(response):
    user = ""
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        try:
            if auth_settings.OIDC_ENABLED:
                token_string = request.headers.get("Authorization").split(" ")[-1]
                user = "User: {}, ".format(get_oauth_userinfo(token_string)['email'])
            else:
                token = request.headers.get("Authorization").split(" ")[-1]
                user = "User: {}, ".format(decode_token(token).get("sub"))
        except Exception:
            user = "User: unknown, "

    try:
        url = re.sub(jwt_query_r, "", request.url)
        if request.headers.get('content-type') == 'application/json':
            logger.info(
                "{}Method: {}, Status: {}, URL: {}, JSON: {}".format(
                    user, request.method, response.status_code, url, request.json
                )
            )
        else:
            logger.info(
                "{}Method: {}, Status: {}, URL: {}".format(
                    user, request.method, response.status_code, url
                )
            )
    except Exception:
        pass
    return response
