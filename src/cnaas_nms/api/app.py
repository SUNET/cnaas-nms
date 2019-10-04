from flask import Flask, render_template
from flask_restful import Api
from flask_socketio import SocketIO, join_room

from cnaas_nms.api.device import DeviceByIdApi, DeviceApi, DevicesApi, \
    LinknetsApi, DeviceInitApi, DeviceSyncApi, DeviceConfigApi, DeviceDiscoverApi
from cnaas_nms.api.interface import InterfaceApi
from cnaas_nms.api.mgmtdomain import MgmtdomainsApi, MgmtdomainByIdApi
from cnaas_nms.api.jobs import JobsApi, JobByIdApi, JobLockApi
from cnaas_nms.api.repository import RepositoryApi
from cnaas_nms.api.settings import SettingsApi
from cnaas_nms.api.groups import GroupsApi, GroupsApiById
from cnaas_nms.api.plugins import PluginsApi
from cnaas_nms.api.firmware import FirmwareApi, FirmwareImageApi

from cnaas_nms.version import __api_version__
import os


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')  # TODO: remove origin * once we have a webUI
app.config['SECRET_KEY'] = os.urandom(128)

api = Api(app, prefix=f'/api/{ __api_version__ }')


# Devices
api.add_resource(DeviceByIdApi, '/device/<int:device_id>')
api.add_resource(DeviceInitApi, '/device_init/<int:device_id>')
api.add_resource(DeviceDiscoverApi, '/device_discover')
api.add_resource(DeviceSyncApi, '/device_syncto')
api.add_resource(DeviceConfigApi, '/device/<string:hostname>/generate_config')
api.add_resource(DeviceApi, '/device')
api.add_resource(DevicesApi, '/devices')
# device/<string:hostname>/current_config

# Links
api.add_resource(LinknetsApi, '/linknets')

# Interfaces
api.add_resource(InterfaceApi, '/device/<string:hostname>/interfaces')

# Management domains
api.add_resource(MgmtdomainsApi, '/mgmtdomains')
api.add_resource(MgmtdomainByIdApi, '/mgmtdomain/<int:mgmtdomain_id>')

# Jobs
api.add_resource(JobsApi, '/jobs')
api.add_resource(JobByIdApi, '/job/<string:id>')
api.add_resource(JobLockApi, '/joblocks')

# File repository
api.add_resource(RepositoryApi, '/repository/<string:repo>')

# Firmware
api.add_resource(FirmwareApi, '/firmware')
api.add_resource(FirmwareImageApi, '/firmware/<string:filename>')

# Settings
api.add_resource(SettingsApi, '/settings')

# Groups
api.add_resource(GroupsApi, '/groups')
api.add_resource(GroupsApiById, '/groups/<string:group_name>')

# Plugins
api.add_resource(PluginsApi, '/plugins')


# SocketIO listen for new log messages
@socketio.on('logs')
def ws_logs(data):
    room: str = None
    if 'level' in data and data['level'] in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        room = data['level']
    elif 'jobid' in data and isinstance(data['jobid'], str):
        room = data['jobid']
    else:
        return False  # TODO: how to send error message to client?

    join_room(room)
