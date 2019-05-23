from flask import request
from flask_restful import Resource
from ipaddress import IPv4Address

import cnaas_nms.confpush.init_device
import cnaas_nms.confpush.sync_devices

from cnaas_nms.api.generic import build_filter, empty_result
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.db.session import sqla_session
from cnaas_nms.scheduler.scheduler import Scheduler


class DeviceByIdApi(Resource):
    def get(self, device_id):
        result = empty_result()
        result['data'] = {'devices': []}
        with sqla_session() as session:
            instance = session.query(Device).filter(Device.id == device_id).one_or_none()
            if instance:
                result['data']['devices'].append(instance.as_dict())
            else:
                return empty_result('error', "Device not found"), 404
        return result

    def delete(self, device_id):
        with sqla_session() as session:
            instance = session.query(Device).filter(Device.id == device_id).one_or_none()
            if instance:
                session.delete(instance)
                session.commit()
                return empty_result(), 200
            else:
                return empty_result('error', "Device not found"), 404

    def put(self, device_id):
        json_data = request.get_json()
        errors = Device.device_update(device_id, **json_data)
        if errors is not None:
            return empty_result(status='error', data=errors), 404
        return empty_result(status='success'), 200


class DevicesApi(Resource):
    def get(self):
        result = empty_result()
        data = {'devices': Device.device_get()}
        return empty_result(status='success', data=data), 200

    def post(self):
        json_data = request.get_json()
        data = {}
        errors = []
        data, errors = Device.validate(**json_data)
        if errors != []:
            return empty_result(status='error', data=errors), 404
        with sqla_session() as session:
            instance: Device = session.query(Device).filter(Device.hostname ==
                                                            data['hostname']).one_or_none()
            if instance is not None:
                errors.append('Device already exists')
                return errors
        Device.device_add(**json_data)
        Device.device_groups_add(**json_data)
        return empty_result(status='success'), 200


class LinknetsApi(Resource):
    def get(self):
        result = {'linknet': []}
        with sqla_session() as session:
            query = session.query(Linknet)
            for instance in query:
                result['linknet'].append(instance.as_dict())
        return empty_result(status='success', data=result)


class DeviceInitApi(Resource):
    def post(self, device_id: int):
        if not isinstance(device_id, int):
            return empty_result(status='error', data="'device_id' must be an integer"), 400

        json_data = request.get_json()
        if 'hostname' not in json_data:
            return empty_result(status='error', data="POST data must include new 'hostname'"), 400
        else:
            if not Device.valid_hostname(json_data['hostname']):
                return empty_result(
                    status='error',
                    data='Provided hostname is not valid'), 400
            else:
                new_hostname = json_data['hostname']

        if 'device_type' not in json_data:
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


class DeviceSyncApi(Resource):
    def post(self):
        json_data = request.get_json()
        kwargs: dict = {}
        if 'hostname' in json_data:
            hostname = str(json_data['hostname'])
            if not Device.valid_hostname(hostname):
                return empty_result(
                    status='error',
                    data=f"Hostname '{hostname}' is not a valid hostname"
                ), 400
            with sqla_session() as session:
                dev: Device = session.query(Device).\
                    filter(Device.hostname == hostname).one_or_none()
                if not dev or dev.state != DeviceState.MANAGED:
                    return empty_result(
                        status='error',
                        data=f"Hostname '{hostname}' not found or is not a managed device"
                    ), 400
            kwargs['hostname'] = hostname
            what = hostname
        elif 'device_type' in json_data:
            if DeviceType.has_name(str(json_data['device_type']).upper()):
                kwargs['device_type'] = DeviceType[str(json_data['device_type']).upper()]
            else:
                return empty_result(
                    status='error',
                    data=f"Invalid device type '{json_data['device_type']}' specified"
                ), 400
            what = f"{json_data['device_type']} devices"
        elif 'all' in json_data and isinstance(json_data['all'], bool) and json_data['all']:
            what = "all devices"
        else:
            return empty_result(
                status='error',
                data=f"No devices to synchronize was specified"
            ), 400

        if 'dry_run' in json_data and isinstance(json_data['dry_run'], bool) \
                and not json_data['dry_run']:
            kwargs['dry_run'] = False

        scheduler = Scheduler()
        job = scheduler.add_onetime_job(
            'cnaas_nms.confpush.sync_devices:sync_devices',
            when=1,
            kwargs=kwargs)

        res = empty_result(data=f"Scheduled job to synchronize {what}")
        res['job_id'] = job.id

        return res

