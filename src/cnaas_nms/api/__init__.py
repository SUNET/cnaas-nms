#!/usr/bin/env python3

from flask import Flask, request
from flask_restful import Resource, Api

import yaml
from ast import literal_eval
from cnaas_nms.cmdb.device import Device, DeviceState
from cnaas_nms.cmdb.linknet import Linknet
from cnaas_nms.cmdb.session import sqla_session

from ipaddress import IPv4Address

app = Flask(__name__)
api = Api(app)

def build_filter(f_class, query):
    args = request.args
    if not 'filter' in args:
        return query
    split = args['filter'].split(',')
    if not len(split) == 2:
        # invalid
        return query
    attribute, value = split
    if not attribute in f_class.__table__._columns.keys():
        # invalid
        return query
    kwargs = {attribute: value}
    return query.filter_by(**kwargs)

def empty_result(status='success', data=None):
    if status == 'success':
        return {
            'status': status,
            'data': None
        }
    elif status == 'error':
        return {
            'status': status,
            'message': data if data else "Unknown error"
        }

class DeviceByIdApi(Resource):
    def get(self, device_id):
        result = empty_result()
        result['data'] = {'devices': []}
        with sqla_session() as session:
            instance = session.query(Device).filter(Device.id == device_id).one()
            if instance:
                result['data']['devices'].append(instance.as_dict())
            else:
                return empty_result('error', "Device not found"), 404
        return result

    def delete(self, device_id):
        with sqla_session() as session:
            instance = session.query(Device).filter(Device.id == device_id).one()
            if instance:
                session.delete(instance)
                session.commit()
                return empty_result(), 204
            else:
                return empty_result('error', "Device not found"), 404

    def put(self, device_id):
        json_data = request.get_json()
        data = {}
        errors = []
        if 'state' in json_data:
            try:
                state_int = int(json_data['state'])
            except:
                errors.append('Invalid device state received.')
            else:
                if DeviceState.has_value(state_int):
                    data['state'] = DeviceState(state_int)
        if 'management_ip' in json_data:
            if json_data['management_ip'] == None:
                data['management_ip'] = None
            else:
                try:
                    addr = IPv4Address(json_data['management_ip'])
                except:
                    errors.append('Invalid management_ip received. Must be correct IPv4 address.')
                else:
                    data['management_ip'] = addr
        with sqla_session() as session:
            instance = session.query(Device).filter(Device.id == device_id).one()
            if instance:
                #TODO: auto loop through class members and match
                if 'state' in data:
                    instance.state = data['state']
                if 'management_ip' in data:
                    instance.management_ip = data['management_ip']


class DevicesApi(Resource):
    def get(self):
        result = []
        filter_exp = None
        with sqla_session() as session:
            query = session.query(Device)
            query = build_filter(Device, query)
            for instance in query:
                result.append(instance.as_dict())
        return result

api.add_resource(DeviceByIdApi, '/api/v1.0/device/<int:device_id>')
api.add_resource(DevicesApi, '/api/v1.0/device')

class LinknetsApi(Resource):
    def get(self):
        result = []
        with sqla_session() as session:
            query = session.query(Linknet)
            for instance in query:
                result.append(instance.as_dict())
        return result

api.add_resource(LinknetsApi, '/api/v1.0/linknet')

class DeviceInit(Resource):
    def post(self):
        pass
