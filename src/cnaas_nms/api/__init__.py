#!/usr/bin/env python3

from flask import Flask
from flask_restful import Api
from cnaas_nms.api.interface import InterfaceApi
from cnaas_nms.api.mgmtdomain import MgmtdomainsApi, MgmtdomainByIdApi
from cnaas_nms.api.jobs import JobsApi
from cnaas_nms.api.repository import RepositoryApi
from cnaas_nms.api.settings import SettingsApi
from cnaas_nms.api.device import DeviceByIdApi, DevicesApi, LinknetsApi, \
    DeviceInitApi, DeviceSyncApi

app = Flask(__name__)
api = Api(app)

api.add_resource(DeviceByIdApi, '/api/v1.0/device/<int:device_id>')
api.add_resource(DevicesApi, '/api/v1.0/device')

api.add_resource(LinknetsApi, '/api/v1.0/linknet')

api.add_resource(DeviceInitApi, '/api/v1.0/device_init/<int:device_id>')
api.add_resource(DeviceSyncApi, '/api/v1.0/device_sync')
api.add_resource(InterfaceApi, '/api/v1.0/device/<string:hostname>/interfaces')

api.add_resource(MgmtdomainsApi, '/api/v1.0/mgmtdomain')
api.add_resource(MgmtdomainByIdApi, '/api/v1.0/mgmtdomain/<int:mgmtdomain_id>')

api.add_resource(JobsApi, '/api/v1.0/job')

api.add_resource(RepositoryApi, '/api/v1.0/repository/<string:repo>')

api.add_resource(SettingsApi, '/api/v1.0/settings')
