#!/usr/bin/env python3

from flask import Flask
from flask_restful import Api
from cnaas_nms.api.device import DeviceByIdApi, DevicesApi, LinknetsApi, DeviceInitApi
from cnaas_nms.api.mgmtdomain import MgmtdomainsApi, MgmtdomainByIdApi
from cnaas_nms.api.jobs import JobsApi

app = Flask(__name__)
api = Api(app)

api.add_resource(DeviceByIdApi, '/api/v1.0/device/<int:device_id>')
api.add_resource(DevicesApi, '/api/v1.0/device')

api.add_resource(LinknetsApi, '/api/v1.0/linknet')

api.add_resource(DeviceInitApi, '/api/v1.0/device_init/<int:device_id>')

api.add_resource(MgmtdomainsApi, '/api/v1.0/mgmtdomain')
api.add_resource(MgmtdomainByIdApi, '/api/v1.0/mgmtdomain/<int:mgmtdomain_id>')

api.add_resource(JobsApi, '/api/v1.0/job')
