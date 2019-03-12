
from flask import request
from flask_restful import Resource
from ipaddress import IPv4Address

import cnaas_nms.confpush.init_device
from cnaas_nms.api.generic import build_filter, empty_result
from cnaas_nms.cmdb.device import Device, DeviceState, DeviceType
from cnaas_nms.cmdb.linknet import Linknet
from cnaas_nms.cmdb.session import sqla_session
from cnaas_nms.scheduler.scheduler import Scheduler

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
                state = str(json_data['state']).upper()
            except:
                errors.append('Invalid device state received.')
            else:
                if DeviceState.has_name(state):
                    data['state'] = DeviceState[state]
                else:
                    errors.append('Invalid device state received.')
        if 'device_type' in json_data:
            try:
                device_type = str(json_data['device_type']).upper()
            except:
                errors.append('Invalid device type received.')
            else:
                if DeviceType.has_name(device_type):
                    data['device_type'] = DeviceType[device_type]
                else:
                    errors.append('Invalid device type received.')
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
                if 'device_type' in data:
                    instance.device_type = data['device_type']
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


class DeviceInitApi(Resource):
    def post(self, device_id: int):
        if not isinstance(device_id, int):
            return empty_result(status='error', data="'device_id' must be an integer"), 400

        json_data = request.get_json()
        if not 'hostname' in json_data:
            return empty_result(status='error', data="POST data must include new 'hostname'"), 400
        else:
            if not Device.valid_hostname(json_data['hostname']):
                return empty_result(
                    status='error',
                    data='Provided hostname is not valid'), 400
            else:
                new_hostname = json_data['hostname']

        if not 'device_type' in json_data:
            return empty_result(status='error', data="POST data must include 'device_type'"), 400
        else:
            try:
                device_type = str(json_data['device_type']).upper()
            except:
                return empty_result(status='error', data="'device_type' must be a string"), 400

            if not DeviceType.has_name(device_type):
                return empty_result(status='error', data="Invalid 'device_type' provided"), 400

        if device_type == DeviceType.ACCESS.name:
            scheduler = Scheduler()
            job = scheduler.add_onetime_job(
                'cnaas_nms.confpush.init_device:init_access_device_step1',
                when=1,
                kwargs={'device_id': device_id, 'new_hostname': new_hostname})

        res = empty_result(data=f"Scheduled job to initialize device_id { device_id }")
        res['job_id'] = job.id

        return res
