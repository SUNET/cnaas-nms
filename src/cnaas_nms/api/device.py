from flask import request
from flask_restful import Resource

import cnaas_nms.confpush.init_device
import cnaas_nms.confpush.sync_devices

from cnaas_nms.api.generic import build_filter, empty_result
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.session import sqla_session
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.tools.log import get_logger
from flask_jwt_extended import jwt_required


logger = get_logger()


class DeviceByIdApi(Resource):
    @jwt_required
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

    @jwt_required
    def delete(self, device_id):
        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.id == device_id).one_or_none()
            if dev:
                session.delete(dev)
                session.commit()
                return empty_result(status="success", data={"deleted_device": dev.as_dict()}), 200
            else:
                return empty_result('error', "Device not found"), 404

    @jwt_required
    def put(self, device_id):
        json_data = request.get_json()
        with sqla_session() as session:
            dev: Device = session.query(Device).filter(
                Device.id == device_id).one_or_none()

            if not dev:
                return empty_result(status='error', data=f"No device with id {device_id}")

            errors = dev.device_update(**json_data)
            if errors is not None:
                return empty_result(status='error', data=errors), 404
            return empty_result(status='success', data={"updated_device": dev.as_dict()}), 200


class DeviceApi(Resource):
    @jwt_required
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
        with sqla_session() as session:
            new_device = Device.device_create(**json_data)
            session.add(new_device)
            session.flush()
            return empty_result(status='success', data={"added_device": new_device.as_dict()}), 200


class DevicesApi(Resource):
    @jwt_required
    def get(self):
        data = {'devices': []}
        with sqla_session() as session:
            query = session.query(Device)
            query = build_filter(Device, query)
            for instance in query:
                data['devices'].append(instance.as_dict())

        return empty_result(status='success', data=data), 200


class DeviceInitApi(Resource):
    @jwt_required
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
            job_id = scheduler.add_onetime_job(
                'cnaas_nms.confpush.init_device:init_access_device_step1',
                when=1,
                kwargs={'device_id': device_id, 'new_hostname': new_hostname})

        res = empty_result(data=f"Scheduled job to initialize device_id { device_id }")
        res['job_id'] = job_id

        return res


class DeviceDiscoverApi(Resource):
    @jwt_required
    def post(self):
        json_data = request.get_json()
        if 'ztp_mac' not in json_data:
            return empty_result(status='error', data="POST data must include 'ztp_mac'"), 400
        if 'dhcp_ip' not in json_data:
            return empty_result(status='error', data="POST data must include 'dhcp_ip'"), 400
        ztp_mac = json_data['ztp_mac']
        dhcp_ip = json_data['dhcp_ip']

        job_id = cnaas_nms.confpush.init_device.schedule_discover_device(
            ztp_mac=ztp_mac, dhcp_ip=dhcp_ip, iteration=1)

        logger.debug(f"Discover device for ztp_mac {ztp_mac} scheduled as ID {job_id}")

        res = empty_result(data=f"Scheduled job to discover device for ztp_mac {ztp_mac}")
        res['job_id'] = job_id

        return res


class DeviceSyncApi(Resource):
    @jwt_required
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
                kwargs['device_type'] = str(json_data['device_type']).upper()
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
        if 'force' in json_data and isinstance(json_data['force'], bool):
            kwargs['force'] = json_data['force']
        if 'auto_push' in json_data and isinstance(json_data['auto_push'], bool):
            kwargs['auto_push'] = json_data['auto_push']

        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.confpush.sync_devices:sync_devices',
            when=1,
            kwargs=kwargs)

        res = empty_result(data=f"Scheduled job to synchronize {what}")
        res['job_id'] = job_id

        return res


class DeviceConfigApi(Resource):
    @jwt_required
    def get(self, hostname: str):
        result = empty_result()
        result['data'] = {'config': None}
        if not Device.valid_hostname(hostname):
            return empty_result(
                status='error',
                data=f"Invalid hostname specified"
            ), 400

        try:
            config, template_vars = cnaas_nms.confpush.sync_devices.generate_only(hostname)
            result['data']['config'] = {
                'hostname': hostname,
                'generated_config': config,
                'available_variables': template_vars
            }
        except Exception as e:
            logger.exception(f"Exception while generating config for device {hostname}")
            return empty_result(
                status='error',
                data="Exception while generating config for device {}: {} {}".format(hostname, type(e), str(e))
            ), 500

        return result
