#!/usr/bin/env python3

from flask import Flask
from flask_restful import Resource, Api

import yaml
from cnaas_nms.cmdb.device import Device
from cnaas_nms.cmdb.session import session_scope

app = Flask(__name__)
api = Api(app)

class DeviceApi(Resource):
    def get(self, device_id):
        result = []
        with session_scope() as session:
            for instance in session.query(Device):
                result.append({
                    'id': instance.id,
                    'description': instance.description
                })

        return result

api.add_resource(DeviceApi, '/api/v1.0/device/<int:device_id>')

