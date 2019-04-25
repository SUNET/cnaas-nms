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


class DeviceValidate(object):
    def json_validate(json_data):
        data = {}
        errors = []

        if 'hostname' in json_data:
            if Device.valid_hostname(json_data['hostname']):
                data['hostname'] = json_data['hostname']
            else:
                errors.append("Invalid hostname received")

        if 'site_id' in json_data:
            data['site_id'] = json_data['site_id']
        else:
            data['site_id'] = None

        if 'description' in json_data:
            data['description'] = json_data['description']

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

        if 'dhcp_ip' in json_data:
            if json_data['dhcp_ip'] == None:
                data['dhcp_ip'] = None
            else:
                try:
                    addr = IPv4Address(json_data['dhcp_ip'])
                except:
                    errors.append('Invalid dhcp_ip received. Must be correct IPv4 address.')
                else:
                    data['dhcp_ip'] = addr

        if 'serial' in json_data:
            try:
                serial = str(json_data['serial']).upper()
            except:
                errors.append('Invalid device serial received.')
            else:
                data['serial'] = serial

        if 'ztp_mac' in json_data:
            try:
                ztp_mac = str(json_data['ztp_mac']).upper()
            except:
                errors.append('Invalid device ztp_mac received.')
            else:
                data['ztp_mac'] = ztp_mac

        if 'platform' in json_data:
            data['platform'] = json_data['platform']

        if 'vendor' in json_data:
            data['vendor'] = json_data['vendor']

        if 'model' in json_data:
            data['model'] = json_data['model']

        if 'os_version' in json_data:
            data['os_version'] = json_data['os_version']

        if 'synchronized' in json_data:  # TODO: disable this for production release?
            if isinstance(json_data['synchronized'], bool):
                data['synchronized'] = json_data['synchronized']
            else:
                errors.append("Invalid synchronization state received")

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
                data['device_type'] = device_type

        return data, errors


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
        data = {}
        errors = []
        data, errors = DeviceValidate.json_validate(json_data)
        if errors != []:
            return empty_result(status='error', data=errors), 404
        with sqla_session() as session:
            instance: Device = session.query(Device).filter(Device.id == device_id).one_or_none()
            if instance:
                #TODO: auto loop through class members and match
                if 'state' in data:
                    instance.state = data['state']
                if 'device_type' in data:
                    instance.device_type = data['device_type']
                if 'management_ip' in data:
                    instance.management_ip = data['management_ip']
                if 'dhcp_ip' in data:
                    instance.dhcp_ip = data['dhcp_ip']
                if 'hostname' in data:
                    instance.hostname = data['hostname']
                if 'synchronized' in data:
                    instance.synchronized = data['synchronized']
                if 'site_id' in data:
                    instance.site_id = data['site_id']
                if 'description' in data:
                    instance.description = data['description']
                if 'state' in data:
                    instance.state = data['state']
                if 'serial' in data:
                    instance.serial = data['serial']
                if 'ztp_mac' in data:
                    instance.ztp_mac = data['ztp_mac']
                if 'platform' in data:
                    instance.platform = data['platform']
                if 'vendor' in data:
                    instance.vendor = data['vendor']
                if 'model' in data:
                    instance.model = data['model']
                if 'os_version' in data:
                    instance.os_version = data['os_version']
            else:
                errors.append('Device not found')
        if errors != []:
            return empty_result(status='error', data=errors), 404
        return empty_result(status='success'), 200

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

    def post(self):
        json_data = request.get_json()
        data = {}
        errors = []
        data, errors = DeviceValidate.json_validate(json_data)
        if errors != []:
            return empty_result(status='error', data=errors), 404
        with sqla_session() as session:
            instance: Device = session.query(Device).filter(Device.hostname == data['hostname']).one_or_none()
            if instance != None:
                errors.append('Device already exists')
                return errors
            new_device = Device()

            if 'hostname' in data:
                new_device.hostname = data['hostname']
            if 'site_id' in data:
                new_device.site_id = data['site_id']
            if 'description' in data:
                new_device.description = data['description']
            if 'management_ip' in data:
                new_device.management_ip = data['management_ip']
            if 'dhcp_ip' in data:
                new_device.dhcp_ip = data['dhcp_ip']
            if 'state' in data:
                new_device.state = data['state']
            if 'serial' in data:
                new_device.serial = data['serial']
            if 'ztp_mac' in data:
                new_device.ztp_mac = data['ztp_mac']
            if 'platform' in data:
                new_device.platform = data['platform']
            if 'vendor' in data:
                new_device.vendor = data['vendor']
            if 'model' in data:
                new_device.model = data['model']
            if 'os_version' in data:
                new_device.os_version = data['os_version']
            if 'synchronized' in data:
                new_device.synchronized = data['synchronized']
            if 'state' in data:
                new_device.state = data['state']
            if 'device_type' in data:
                new_device.device_type = data['device_type']

            session.add(new_device)
        return empty_result(status='success'), 200


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

