import os
import re
import sys
from typing import Optional

from authlib.integrations.flask_client import OAuth
from engineio.payload import Payload
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_jwt_extended.exceptions import InvalidHeaderError, NoAuthorizationError
from flask_restx import Api
from flask_socketio import SocketIO, join_room
from jwt.exceptions import (
    DecodeError,
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidSignatureError,
    InvalidTokenError,
)

from cnaas_nms.api.auth import api as auth_api
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
from cnaas_nms.app_settings import api_settings, auth_settings
from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.security import get_identity, login_required
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
            return jsonify(data), 401
        elif isinstance(e, InvalidAudienceError):
            data = {"status": "error", "message": "You don't seem to have the rights to execute this call"}
            return jsonify(data), 403
        elif isinstance(e, ExpiredSignatureError):
            data = {"status": "error", "message": "The JWT token is expired", "errorCode": "auth_expired"}
            return jsonify(data), 401
        elif isinstance(e, InvalidTokenError):
            data = {"status": "error", "message": "Invalid authentication header: {}".format(e)}
            return jsonify(data), 401
        elif isinstance(e, InvalidSignatureError):
            data = {"status": "error", "message": "Invalid token signature"}
            return jsonify(data), 401
        elif isinstance(e, IndexError):
            # We might catch IndexErrors which are not caused by JWT,
            # but this is better than nothing.
            data = {"status": "error", "message": "JWT token missing?"}
            return jsonify(data), 401
        elif isinstance(e, NoAuthorizationError):
            data = {"status": "error", "message": "JWT token missing?"}
            return jsonify(data), 401
        elif isinstance(e, InvalidHeaderError):
            data = {"status": "error", "message": "Invalid header, JWT token missing? {}".format(e)}
            return jsonify(data), 401
        else:
            return super(CnaasApi, self).handle_error(e)
        
       


app = Flask(__name__)

# To register the OAuth client
oauth = OAuth(app)
client = oauth.register(
    "connext",
    server_metadata_url=auth_settings.OIDC_CONF_WELL_KNOWN_URL,
    client_id=auth_settings.OIDC_CLIENT_ID,
    client_secret=auth_settings.OIDC_CLIENT_SECRET,
    client_kwargs={"scope": "openid"},
    response_type="code",
    response_mode="query",
)

if api_settings.JWT_ENABLED:
    app.config["SECRET_KEY"] = os.urandom(128)

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
@login_required
def socketio_on_connect():
    user = get_identity()
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
    try:
        url = re.sub(jwt_query_r, "", request.url)
        if request.headers.get("content-type") == "application/json":
            logger.info(
                "Method: {}, Status: {}, URL: {}, JSON: {}".format(
                    request.method, response.status_code, url, request.json
                )
            )
        else:
            logger.info("Method: {}, Status: {}, URL: {}".format(request.method, response.status_code, url))
    except Exception:
        pass
    return response
