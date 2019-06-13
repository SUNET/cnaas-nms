from flask import Flask
from flask_restful import Api
from cnaas_nms.api.device import DeviceByIdApi, DevicesApi, LinknetsApi, \
    DeviceInitApi, DeviceSyncApi
from cnaas_nms.api.interface import InterfaceApi
from cnaas_nms.api.mgmtdomain import MgmtdomainsApi, MgmtdomainByIdApi
from cnaas_nms.api.jobs import JobsApi
from cnaas_nms.api.repository import RepositoryApi
from cnaas_nms.api.settings import SettingsApi
from cnaas_nms.api.groups import GroupsApi, GroupsApiById

from cnaas_nms.version import __api_version__


app = Flask(__name__)
api = Api(app)

# Devices
api.add_resource(DeviceByIdApi, f'/api/{ __api_version__ }/device/<int:device_id>')
api.add_resource(DevicesApi, f'/api/{ __api_version__ }/device')
api.add_resource(DeviceInitApi, f'/api/{ __api_version__ }/device_init/<int:device_id>')
api.add_resource(DeviceSyncApi, f'/api/{ __api_version__ }/device_syncto')

# Links
api.add_resource(LinknetsApi, f'/api/{ __api_version__ }/linknet')

# Interfaces
api.add_resource(InterfaceApi, f'/api/{ __api_version__ }/device/<string:hostname>/interfaces')

# Management domains
api.add_resource(MgmtdomainsApi, f'/api/{ __api_version__ }/mgmtdomain')
api.add_resource(MgmtdomainByIdApi, f'/api/{ __api_version__ }/mgmtdomain/<int:mgmtdomain_id>')

# Jobs
api.add_resource(JobsApi, f'/api/{ __api_version__ }/job')

# File repository
api.add_resource(RepositoryApi, f'/api/{ __api_version__ }/repository/<string:repo>')

# Settings
api.add_resource(SettingsApi, f'/api/{ __api_version__ }/settings')

# Groups
api.add_resource(GroupsApi, f'/api/{ __api_version__ }/groups')
api.add_resource(GroupsApiById, f'/api/{ __api_version__ }/groups/<string:group_name>')

# Device groups
api.add_resource(DeviceGroupsApi, f'/api/{ __api_version__ }/groups/<string:group_name>/devices')
api.add_resource(DeviceGroupsApiById, f'/api/{ __api_version__ }/groups/<string:group_name>/devices/<int:device_id>')
>>>>>>> master
