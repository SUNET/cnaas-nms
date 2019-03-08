
from flask import request
from flask_restful import Resource
from ipaddress import IPv4Address

from cnaas_nms.api.generic import build_filter, empty_result
from cnaas_nms.cmdb.device import Device, DeviceState
from cnaas_nms.cmdb.linknet import Linknet
from cnaas_nms.cmdb.session import sqla_session

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
        if 'hostname' in json_data:
            if Device.valid_hostname(json_data['hostname']):
                data['hostname'] = json_data['hostname']
            else:
                errors.append("Invalid hostname received")
        with sqla_session() as session:
            instance = session.query(Device).filter(Device.id == device_id).one()
            if instance:
                #TODO: auto loop through class members and match
                if 'state' in data:
                    instance.state = data['state']
                if 'management_ip' in data:
                    instance.management_ip = data['management_ip']
                if 'hostname' in data:
                    instance.hostname = data['hostname']


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


class LinknetsApi(Resource):
    def get(self):
        result = []
        with sqla_session() as session:
            query = session.query(Linknet)
            for instance in query:
                result.append(instance.as_dict())
        return result


class DeviceInit(Resource):
    def post(self):
        pass
