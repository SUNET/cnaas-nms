import json
from typing import Optional

from flask import request, make_response
from flask_restplus import Resource, Namespace, fields
from sqlalchemy import func

import cnaas_nms.confpush.init_device
import cnaas_nms.confpush.sync_devices
import cnaas_nms.confpush.underlay
from cnaas_nms.api.generic import build_filter, empty_result
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.session import sqla_session
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.tools.log import get_logger
from flask_jwt_extended import jwt_required
from cnaas_nms.version import __api_version__


logger = get_logger()


device_api = Namespace('device', description='API for handling a single device',
                       prefix='/api/{}'.format(__api_version__))
devices_api = Namespace('devices', description='API for handling devices',
                        prefix='/api/{}'.format(__api_version__))
device_init_api = Namespace('device_init', description='API for init devices',
                            prefix='/api/{}'.format(__api_version__))
device_syncto_api = Namespace('device_syncto', description='API to sync devices',
                              prefix='/api/{}'.format(__api_version__))
device_discover_api = Namespace('device_discover', description='API to discover devices',
                                prefix='/api/{}'.format(__api_version__))


device_model = device_api.model('device', {
    'hostname': fields.String(required=True),
    'site_id': fields.Integer(required=False),
    'description': fields.String(required=False),
    'management_ip': fields.String(required=False),
    'infra_ip': fields.String(required=False),
    'dhcp_ip': fields.String(required=False),
    'serial': fields.String(required=False),
    'ztp_mac': fields.String(required=False),
    'platform': fields.String(required=True),
    'vendor': fields.String(required=False),
    'model': fields.String(required=False),
    'os_version': fields.String(required=False),
    'synchronized': fields.Boolean(required=False),
    'state': fields.String(required=True),
    'device_type': fields.String(required=True),
    'port': fields.Integer(required=False)})

device_init_model = device_init_api.model('device_init', {
    'hostname': fields.String(required=False),
    'device_type': fields.String(required=False)})

device_discover_model = device_discover_api.model('device_discover', {
    'ztp_mac': fields.String(required=True),
    'dhcp_ip': fields.String(required=True)})

device_syncto_model = device_syncto_api.model('device_sync', {
    'hostname': fields.String(required=False),
    'device_type': fields.String(required=False),
    'all': fields.String(required=False),
    'dry_run': fields.String(required=False),
    'force': fields.String(required=False),
    'auto_push': fields.String(required=False)})


class DeviceByIdApi(Resource):
    @jwt_required
    def get(self, device_id):
        """ Get a device from ID """
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
        """ Delete device from ID """
        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.id == device_id).one_or_none()
            if dev:
                session.delete(dev)
                session.commit()
                return empty_result(status="success", data={"deleted_device": dev.as_dict()}), 200
            else:
                return empty_result('error', "Device not found"), 404

    @jwt_required
    @device_api.expect(device_model)
    def put(self, device_id):
        """ Modify device from ID """
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
    @device_api.expect(device_model)
    def post(self):
        """ Add a device """
        json_data = request.get_json()
        supported_platforms = ['eos', 'junos', 'ios', 'iosxr', 'nxos', 'nxos_ssh']
        data = {}
        errors = []
        data, errors = Device.validate(**json_data)
        if errors != []:
            return empty_result(status='error', data=errors), 400
        with sqla_session() as session:
            instance: Device = session.query(Device).filter(Device.hostname ==
                                                            data['hostname']).one_or_none()
            if instance is not None:
                errors.append('Device already exists')
                return empty_result(status='error', data=errors), 400
            if 'platform' not in data or data['platform'] not in supported_platforms:
                errors.append("Device platform not specified or not known (must be any of: {})".
                              format(', '.join(supported_platforms)))
                return empty_result(status='error', data=errors), 400
            if data['device_type'] in ['DIST', 'CORE']:
                if 'management_ip' not in data or not data['management_ip']:
                    data['management_ip'] = cnaas_nms.confpush.underlay.find_free_mgmt_lo_ip(session)
                if 'infra_ip' not in data or not data['infra_ip']:
                    data['infra_ip'] = cnaas_nms.confpush.underlay.find_free_infra_ip(session)
            new_device = Device.device_create(**data)
            session.add(new_device)
            session.flush()
            return empty_result(status='success', data={"added_device": new_device.as_dict()}), 200


class DevicesApi(Resource):
    @jwt_required
    def get(self):
        """ Get all devices """
        data = {'devices': []}
        total_count = 0
        with sqla_session() as session:
            query = session.query(Device, func.count(Device.id).over().label('total'))
            query = build_filter(Device, query)
            for instance in query:
                data['devices'].append(instance.Device.as_dict())
                total_count = instance.total

        resp = make_response(json.dumps(empty_result(status='success', data=data)), 200)
        resp.headers['X-Total-Count'] = total_count
        return resp


class DeviceInitApi(Resource):
    @jwt_required
    @device_init_api.expect(device_init_model)
    def post(self, device_id: int):
        """ Init a device """
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
    @device_discover_api.expect(device_discover_model)
    def post(self):
        """ Discover device """
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
    @device_syncto_api.expect(device_syncto_model)
    def post(self):
        """ Start sync of device(s) """
        json_data = request.get_json()
        kwargs: dict = {}
        total_count: Optional[int] = None
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
            total_count = 1
        elif 'device_type' in json_data:
            devtype_str = str(json_data['device_type']).upper()
            if DeviceType.has_name(devtype_str):
                kwargs['device_type'] = devtype_str
            else:
                return empty_result(
                    status='error',
                    data=f"Invalid device type '{json_data['device_type']}' specified"
                ), 400
            what = f"{json_data['device_type']} devices"
            with sqla_session() as session:
                total_count = session.query(Device). \
                    filter(Device.device_type == DeviceType[devtype_str]).count()
        elif 'all' in json_data and isinstance(json_data['all'], bool) and json_data['all']:
            what = "all devices"
            with sqla_session() as session:
                total_count = session.query(Device). \
                    filter(Device.state == DeviceState.MANAGED). \
                    filter(Device.synchronized == False).count()
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

        resp = make_response(json.dumps(res), 200)
        if total_count:
            resp.headers['X-Total-Count'] = total_count
        resp.headers['Content-Type'] = "application/json"
        return resp


class DeviceConfigApi(Resource):
    @jwt_required
    def get(self, hostname: str):
        """ Get device configuration """
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


# Devices
device_api.add_resource(DeviceByIdApi, '/<int:device_id>')
device_api.add_resource(DeviceConfigApi, '/<string:hostname>/generate_config')
device_api.add_resource(DeviceApi, '')
devices_api.add_resource(DevicesApi, '')
device_init_api.add_resource(DeviceInitApi, '/<int:device_id>')
device_discover_api.add_resource(DeviceDiscoverApi, '')
device_syncto_api.add_resource(DeviceSyncApi, '')
# device/<string:hostname>/current_config
