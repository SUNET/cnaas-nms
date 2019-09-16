from flask import Flask, render_template
from flask_restful import Api
from cnaas_nms.api.device import DeviceByIdApi, DevicesApi, LinknetsApi, \
    DeviceInitApi, DeviceSyncApi, DeviceConfigApi
from cnaas_nms.api.interface import InterfaceApi
from cnaas_nms.api.mgmtdomain import MgmtdomainsApi, MgmtdomainByIdApi
from cnaas_nms.api.jobs import JobsApi, JobByIdApi, JobLockApi
from cnaas_nms.api.repository import RepositoryApi
from cnaas_nms.api.settings import SettingsApi
from cnaas_nms.api.groups import GroupsApi, GroupsApiById
from cnaas_nms.api.plugins import PluginsApi

from cnaas_nms.version import __api_version__
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(128)

api = Api(app)


# Devices
api.add_resource(DeviceByIdApi, f'/api/{ __api_version__ }/device/<int:device_id>')
api.add_resource(DeviceInitApi, f'/api/{ __api_version__ }/device_init/<int:device_id>')
api.add_resource(DeviceSyncApi, f'/api/{ __api_version__ }/device_syncto')
api.add_resource(DeviceConfigApi, f'/api/{ __api_version__ }/device/<string:hostname>/generate_config')
api.add_resource(DevicesApi, f'/api/{ __api_version__ }/devices')
# device/<string:hostname>/current_config

# Links
api.add_resource(LinknetsApi, f'/api/{ __api_version__ }/linknet')

# Interfaces
api.add_resource(InterfaceApi, f'/api/{ __api_version__ }/device/<string:hostname>/interfaces')

# Management domains
api.add_resource(MgmtdomainsApi, f'/api/{ __api_version__ }/mgmtdomain')
api.add_resource(MgmtdomainByIdApi, f'/api/{ __api_version__ }/mgmtdomain/<int:mgmtdomain_id>')

# Jobs
api.add_resource(JobsApi, f'/api/{ __api_version__ }/job')
api.add_resource(JobByIdApi, f'/api/{ __api_version__ }/job/<string:id>')
api.add_resource(JobLockApi, f'/api/{ __api_version__ }/joblocks')

# File repository
api.add_resource(RepositoryApi, f'/api/{ __api_version__ }/repository/<string:repo>')

# Settings
api.add_resource(SettingsApi, f'/api/{ __api_version__ }/settings')

# Groups
api.add_resource(GroupsApi, f'/api/{ __api_version__ }/groups')
api.add_resource(GroupsApiById, f'/api/{ __api_version__ }/groups/<string:group_name>')

# Plugins
api.add_resource(PluginsApi, f'/api/{ __api_version__ }/plugins')
