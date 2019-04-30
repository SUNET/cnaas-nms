#!/usr/bin/env python3

from flask import Flask
from flask_restful import Api
from cnaas_nms.api.device import DeviceByIdApi, DevicesApi, LinknetsApi, \
    DeviceInitApi, DeviceSyncApi
from cnaas_nms.api.interface import InterfaceApi
from cnaas_nms.api.mgmtdomain import MgmtdomainsApi, MgmtdomainByIdApi
from cnaas_nms.api.jobs import JobsApi
from cnaas_nms.api.repository import RepositoryApi

from cnaas_nms.api.settings import SettingsApi
from cnaas_nms.api.groups import GroupsApi
from cnaas_nms.api.groups import GroupsApiByName
from cnaas_nms.api.query import QueryApi


API_VERSION = 'v1.0'

app = Flask(__name__)
api = Api(app)

# Devices
api.add_resource(DeviceByIdApi, f'/api/{ API_VERSION }/device/<int:device_id>')
api.add_resource(DevicesApi, f'/api/{ API_VERSION }/device')
api.add_resource(DeviceInitApi, f'/api/{ API_VERSION }/device_init/<int:device_id>')
api.add_resource(DeviceSyncApi, f'/api/{ API_VERSION }/device_sync')

# Links
api.add_resource(LinknetsApi, f'/api/{ API_VERSION }/linknet')

# Interfaces
api.add_resource(InterfaceApi, f'/api/{ API_VERSION }/device/<string:hostname>/interfaces')

# Management domains
api.add_resource(MgmtdomainsApi, f'/api/{ API_VERSION }/mgmtdomain')
api.add_resource(MgmtdomainByIdApi, f'/api/{ API_VERSION }/mgmtdomain/<int:mgmtdomain_id>')

# Jobs
api.add_resource(JobsApi, f'/api/{ API_VERSION }/job')

# File repository
api.add_resource(RepositoryApi, f'/api/{ API_VERSION }/repository/<string:repo>')

# Query
api.add_resource(QueryApi, f'/api/{ API_VERSION }/query')

# Settings
api.add_resource(RepositoryApi, '/api/v1.0/repository/<string:repo>')
api.add_resource(SettingsApi, '/api/v1.0/settings')

# Groups
api.add_resource(GroupsApi, f'/api/{ API_VERSION }/groups')
api.add_resource(GroupsApiByName, f'/api/{ API_VERSION }/groups/<int:group_id>')
