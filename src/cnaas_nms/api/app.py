import os
import sys
import re
from typing import Optional

from flask import Flask, render_template, request, g
from flask_restx import Api
from flask_socketio import SocketIO, join_room
from flask_jwt_extended import JWTManager, decode_token, jwt_required, get_jwt_identity
from flask_jwt_extended.exceptions import NoAuthorizationError

from flask import jsonify
from flask_cors import CORS

from cnaas_nms.version import __api_version__
from cnaas_nms.tools.log import get_logger

from cnaas_nms.api.device import device_api, devices_api, device_init_api, \
    device_syncto_api, device_discover_api, device_update_facts_api
from cnaas_nms.api.linknet import api as links_api
from cnaas_nms.api.firmware import api as firmware_api
from cnaas_nms.api.interface import api as interfaces_api
from cnaas_nms.api.jobs import job_api, jobs_api, joblock_api
from cnaas_nms.api.mgmtdomain import mgmtdomain_api, mgmtdomains_api
from cnaas_nms.api.groups import api as groups_api
from cnaas_nms.api.repository import api as repository_api
from cnaas_nms.api.settings import api as settings_api
from cnaas_nms.api.plugins import api as plugins_api
from cnaas_nms.api.system import api as system_api
from cnaas_nms.tools.get_apidata import get_apidata

from jwt.exceptions import DecodeError, InvalidSignatureError, \
    InvalidTokenError
from flask_jwt_extended.exceptions import InvalidHeaderError


logger = get_logger()


authorizations = {
    'apikey': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization',
        'description': "Type in 'Bearer: <your JWT token here' to autheticate."
    }
}

jwt_query_r = re.compile(r'jwt=[^ &]+')


class CnaasApi(Api):
    def handle_error(self, e):
        if isinstance(e, DecodeError):
            data = {'status': 'error', 'data': 'Could not deode JWT token'}
        elif isinstance(e, InvalidTokenError):
            data = {'status': 'error', 'data': 'Invalid authentication header'}
        elif isinstance(e, InvalidSignatureError):
            data = {'status': 'error', 'data': 'Invalid token signature'}
        elif isinstance(e, IndexError):
            # We might catch IndexErrors which are not cuased by JWT,
            # but this is better than nothing.
            data = {'status': 'error', 'data': 'JWT token missing?'}
        elif isinstance(e, NoAuthorizationError):
            data = {'status': 'error', 'data': 'JWT token missing?'}
        elif isinstance(e, InvalidHeaderError):
            data = {'status': 'error', 'data': 'Invalid header, JWT token missing? {}'.format(e)}
        else:
            return super(CnaasApi, self).handle_error(e)
        return jsonify(data), 401


try:
    jwt_pubkey = open(get_apidata()['jwtcert']).read()
except Exception as e:
    print("Could not load public JWT cert from api.yml config: {}".format(e))
    sys.exit(1)

app = Flask(__name__)
# TODO: make origins configurable
cors = CORS(app,
            resources={r"/api/*": {"origins": "*"}},
            expose_headers=["Content-Type", "Authorization", "X-Total-Count"])
socketio = SocketIO(app, cors_allowed_origins='*')
app.config['SECRET_KEY'] = os.urandom(128)
app.config['JWT_PUBLIC_KEY'] = jwt_pubkey
app.config['JWT_IDENTITY_CLAIM'] = 'sub'
app.config['JWT_ALGORITHM'] = 'ES256'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False
app.config['JWT_TOKEN_LOCATION'] = ('headers', 'query_string')

jwt = JWTManager(app)
api = CnaasApi(app, prefix='/api/{}'.format(__api_version__),
               authorizations=authorizations,
               security='apikey')

api.add_namespace(device_api)
api.add_namespace(devices_api)
api.add_namespace(device_init_api)
api.add_namespace(device_syncto_api)
api.add_namespace(device_discover_api)
api.add_namespace(device_update_facts_api)
api.add_namespace(links_api)
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
@socketio.on('connect')
@jwt_required
def socketio_on_connect():
    user = get_jwt_identity()
    if user:
        logger.info('User: {} connected via socketio'.format(user))
        return True
    else:
        return False

# SocketIO join event rooms
@socketio.on('events')
def socketio_on_events(data):
    room: Optional[str] = None
    if 'loglevel' in data and data['loglevel'] in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        room = data['loglevel']
    elif 'update' in data and data['update'] in ['device', 'job']:
        room = "update_{}".format(data['update'])
    else:
        return False  # TODO: how to send error message to client?

    join_room(room)


# Log all requests, include username etc
@app.after_request
def log_request(response):
    try:
        token = request.headers.get('Authorization').split(' ')[-1]
        user = decode_token(token).get('sub')
    except Exception:
        user = 'unknown'
    try:
        url = re.sub(jwt_query_r, '', request.url)
        logger.info('User: {}, Method: {}, Status: {}, URL: {}, JSON: {}'.format(
            user, request.method, response.status_code, url, request.json))
    except Exception:
        pass
    return response
