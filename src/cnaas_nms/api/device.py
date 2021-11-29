import json
import datetime
from typing import Optional

from flask import request, make_response
from flask_restx import Resource, Namespace, fields
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

import cnaas_nms.confpush.init_device
import cnaas_nms.confpush.sync_devices
import cnaas_nms.confpush.underlay
import cnaas_nms.confpush.get
import cnaas_nms.confpush.update
from cnaas_nms.confpush.nornir_helper import cnaas_init, inventory_selector
from cnaas_nms.api.generic import build_filter, empty_result
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.job import Job, JobNotFoundError, InvalidJobError
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.settings import get_groups
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.tools.log import get_logger
from flask_jwt_extended import jwt_required, get_jwt_identity
from cnaas_nms.version import __api_version__
from cnaas_nms.tools.get_apidata import get_apidata


logger = get_logger()


device_api = Namespace('device', description='API for handling a single device',
                       prefix='/api/{}'.format(__api_version__))
devices_api = Namespace('devices', description='API for handling devices',
                        prefix='/api/{}'.format(__api_version__))
device_init_api = Namespace('device_init', description='API for init devices',
                            prefix='/api/{}'.format(__api_version__))
device_initcheck_api = Namespace('device_initcheck', description='API for init check of devices',
                                 prefix='/api/{}'.format(__api_version__))
device_syncto_api = Namespace('device_syncto', description='API to sync devices',
                              prefix='/api/{}'.format(__api_version__))
device_discover_api = Namespace('device_discover', description='API to discover devices',
                                prefix='/api/{}'.format(__api_version__))
device_update_facts_api = Namespace('device_update_facts',
                                    description='API to update facts about devices',
                                    prefix='/api/{}'.format(__api_version__))
device_update_interfaces_api = Namespace('device_update_interfaces',
                                         description='API to update/scan device interfaces',
                                         prefix='/api/{}'.format(__api_version__))
device_cert_api = Namespace('device_cert', description='API to handle device certificates',
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

device_initcheck_model = device_initcheck_api.model('device_initcheck', {
    'hostname': fields.String(required=False),
    'device_type': fields.String(required=False)})

device_discover_model = device_discover_api.model('device_discover', {
    'ztp_mac': fields.String(required=True),
    'dhcp_ip': fields.String(required=True)})

device_syncto_model = device_syncto_api.model('device_sync', {
    'hostname': fields.String(required=False),
    'device_type': fields.String(required=False),
    'group': fields.String(required=False),
    'all': fields.Boolean(required=False),
    'dry_run': fields.Boolean(required=False),
    'force': fields.Boolean(required=False),
    'auto_push': fields.Boolean(required=False),
    'resync': fields.Boolean(required=False)
})

device_update_facts_model = device_syncto_api.model('device_update_facts', {
    'hostname': fields.String(required=True),
})

device_update_interfaces_model = device_syncto_api.model('device_update_interfaces', {
    'hostname': fields.String(required=True),
    'replace': fields.Boolean(required=False),
    'delete_all': fields.Boolean(required=False),
})

device_restore_model = device_api.model('device_restore', {
    'dry_run': fields.Boolean(required=False),
    'job_id': fields.Integer(required=True),
})

device_apply_config_model = device_api.model('device_apply_config', {
    'dry_run': fields.Boolean(required=False),
    'full_config': fields.String(required=True),
})

device_cert_model = device_syncto_api.model('device_cert', {
    'hostname': fields.String(required=False,
                              description="Device hostname",
                              example="myhostname"),
    'group': fields.String(required=False,
                           description="Device group",
                           example="mygroup"),
    'action': fields.String(required=True,
                            description="Action to execute, one of: RENEW",
                            example="RENEW")
})


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
        json_data = request.get_json()

        if json_data and 'factory_default' in json_data:
            if isinstance(json_data['factory_default'], bool) and json_data['factory_default'] is True:
                scheduler = Scheduler()
                job_id = scheduler.add_onetime_job(
                    'cnaas_nms.confpush.erase:device_erase',
                    when=1,
                    scheduled_by=get_jwt_identity(),
                    kwargs={'device_id': device_id})
                return empty_result(data='Scheduled job {} to factory default device'.format(job_id))
            elif not isinstance(json_data['factory_default'], bool):
                return empty_result(status='error', data="Argument factory_default must be boolean"), 400
        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.id == device_id).one_or_none()
            if not dev:
                return empty_result('error', "Device not found"), 404
            try:
                session.delete(dev)
                session.commit()
            except IntegrityError as e:
                session.rollback()
                return empty_result(
                    status='error',
                    data="Could not remove device because existing references: {}".format(e))
            except Exception as e:
                session.rollback()
                return empty_result(
                    status='error',
                    data="Could not remove device: {}".format(e))
            return empty_result(status="success", data={"deleted_device": dev.as_dict()}), 200

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
            if errors:
                return empty_result(status='error', data=errors), 404
            return empty_result(status='success', data={"updated_device": dev.as_dict()}), 200


class DeviceByHostnameApi(Resource):
    @jwt_required
    def get(self, hostname):
        """ Get a device from hostname """
        result = empty_result()
        result['data'] = {'devices': []}
        with sqla_session() as session:
            instance = session.query(Device).filter(Device.hostname == hostname).one_or_none()
            if instance:
                result['data']['devices'].append(instance.as_dict())
            else:
                return empty_result('error', "Device not found"), 404
        return result


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
            if instance:
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
            try:
                query = build_filter(Device, query)
            except Exception as e:
                return empty_result(status='error',
                                    data="Unable to filter devices: {}".format(e)), 400
            for instance in query:
                data['devices'].append(instance.Device.as_dict())
                total_count = instance.total

        resp = make_response(json.dumps(empty_result(status='success', data=data)), 200)
        resp.headers['X-Total-Count'] = total_count
        resp.headers['Content-Type'] = 'application/json'
        return resp


class DeviceInitApi(Resource):
    @jwt_required
    @device_init_api.expect(device_init_model)
    def post(self, device_id: int):
        """ Init a device """
        json_data = request.get_json()
        try:
            job_kwargs = self.arg_check(device_id, json_data)
        except ValueError as e:
            return empty_result(status='error', data=str(e)), 400

        # If device init is already in progress, reschedule a new step2 (connectivity check)
        # instead of trying to restart initialization
        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.id == device_id).one_or_none()
            if dev and dev.state == DeviceState.INIT and \
                    dev.management_ip and dev.device_type is not DeviceType.UNKNOWN:
                scheduler = Scheduler()
                job_id = scheduler.add_onetime_job(
                    'cnaas_nms.confpush.init_device:init_device_step2',
                    when=1,
                    scheduled_by=get_jwt_identity(),
                    kwargs={'device_id': device_id, 'iteration': 1})

                logger.info("Re-scheduled init step 2 for {} as job # {}".format(
                    device_id, job_id
                ))
                res = empty_result(data=f"Re-scheduled init step 2 for device_id { device_id }")
                res['job_id'] = job_id
                return res

        if job_kwargs['device_type'] == DeviceType.ACCESS.name:
            del job_kwargs['device_type']
            del job_kwargs['neighbors']
            scheduler = Scheduler()
            job_id = scheduler.add_onetime_job(
                'cnaas_nms.confpush.init_device:init_access_device_step1',
                when=1,
                scheduled_by=get_jwt_identity(),
                kwargs=job_kwargs)
        elif job_kwargs['device_type'] in [DeviceType.CORE.name, DeviceType.DIST.name]:
            scheduler = Scheduler()
            job_id = scheduler.add_onetime_job(
                'cnaas_nms.confpush.init_device:init_fabric_device_step1',
                when=1,
                scheduled_by=get_jwt_identity(),
                kwargs=job_kwargs)
        else:
            return empty_result(status='error', data="Unsupported 'device_type' provided"), 400

        res = empty_result(data=f"Scheduled job to initialize device_id { device_id }")
        res['job_id'] = job_id

        return res

    @classmethod
    def arg_check(cls, device_id: int, json_data: dict) -> dict:
        parsed_args = {
            'device_id': device_id
        }
        if not isinstance(device_id, int):
            raise ValueError("'device_id' must be an integer")

        if 'hostname' not in json_data:
            raise ValueError("POST data must include new 'hostname'")
        else:
            if not Device.valid_hostname(json_data['hostname']):
                raise ValueError("Provided hostname is not valid")
            else:
                parsed_args['new_hostname'] = json_data['hostname']

        if 'device_type' not in json_data:
            raise ValueError("POST data must include 'device_type'")
        else:
            try:
                device_type = str(json_data['device_type']).upper()
            except Exception:
                raise ValueError("'device_type' must be a string")

            if DeviceType.has_name(device_type):
                parsed_args['device_type'] = device_type
            else:
                raise ValueError("Invalid 'device_type' provided")

        if 'mlag_peer_id' in json_data or 'mlag_peer_hostname' in json_data:
            if 'mlag_peer_id' not in json_data or 'mlag_peer_hostname' not in json_data:
                raise ValueError("Both 'mlag_peer_id' and 'mlag_peer_hostname' must be specified")
            if not isinstance(json_data['mlag_peer_id'], int):
                raise ValueError("'mlag_peer_id' must be an integer")
            if not Device.valid_hostname(json_data['mlag_peer_hostname']):
                raise ValueError("Provided 'mlag_peer_hostname' is not valid")
            parsed_args['mlag_peer_id'] = json_data['mlag_peer_id']
            parsed_args['mlag_peer_new_hostname'] = json_data['mlag_peer_hostname']

        if 'neighbors' in json_data and json_data['neighbors'] is not None:
            if isinstance(json_data['neighbors'], list):
                for neighbor in json_data['neighbors']:
                    if not Device.valid_hostname(neighbor):
                        raise ValueError("Invalid hostname specified in neighbor list")
                parsed_args['neighbors'] = json_data['neighbors']
            else:
                raise ValueError("Neighbors must be specified as either a list of hostnames,"
                                 "an empty list, or not specified at all")
        else:
            parsed_args['neighbors'] = None

        return parsed_args


class DeviceInitCheckApi(Resource):
    @jwt_required
    @device_init_api.expect(device_initcheck_model)
    def post(self, device_id: int):
        """Perform init check on a device"""
        json_data = request.get_json()
        ret = {}
        try:
            parsed_args = DeviceInitApi.arg_check(device_id, json_data)
            target_devtype = DeviceType[parsed_args['device_type']]
            target_hostname = parsed_args['new_hostname']
            mlag_peer_target_hostname: Optional[str] = None
            mlag_peer_id: Optional[int] = None
            mlag_peer_dev: Optional[Device] = None
            if 'mlag_peer_id' in parsed_args and 'mlag_peer_new_hostname' in parsed_args:
                mlag_peer_target_hostname = parsed_args['mlag_peer_new_hostname']
                mlag_peer_id = parsed_args['mlag_peer_id']
        except ValueError as e:
            return empty_result(status='error',
                                data="Error parsing arguments: {}".format(e)), 400

        with sqla_session() as session:
            try:
                dev = cnaas_nms.confpush.init_device.pre_init_checks(session, device_id)
            except ValueError as e:
                return empty_result(status='error',
                                    data="ValueError in pre_init_checks: {}".format(e)), 400
            except Exception as e:
                return empty_result(status='error',
                                    data="Exception in pre_init_checks: {}".format(e)), 500

            if mlag_peer_id:
                try:
                    mlag_peer_dev = cnaas_nms.confpush.init_device.pre_init_checks(
                        session, mlag_peer_id)
                except ValueError as e:
                    return empty_result(status='error',
                                        data="ValueError in pre_init_checks: {}".format(e)), 400
                except Exception as e:
                    return empty_result(status='error',
                                        data="Exception in pre_init_checks: {}".format(e)), 500

            try:
                ret['linknets'] = cnaas_nms.confpush.update.update_linknets(
                    session,
                    hostname=dev.hostname,
                    devtype=target_devtype,
                    ztp_hostname=target_hostname,
                    dry_run=True
                )
                if mlag_peer_dev:
                    ret['linknets'] += cnaas_nms.confpush.update.update_linknets(
                        session,
                        hostname=mlag_peer_dev.hostname,
                        devtype=target_devtype,
                        ztp_hostname=mlag_peer_target_hostname,
                        dry_run=True
                    )
                ret['linknets_compatible'] = True
            except ValueError as e:
                ret['linknets_compatible'] = False
                ret['linknets_error'] = str(e)
            except Exception as e:
                return empty_result(status='error',
                                    data="Exception in update_linknets: {}".format(e)), 500

            try:
                if 'linknets' in ret and ret['linknets']:
                    ret['neighbors'] = cnaas_nms.confpush.init_device.pre_init_check_neighbors(
                        session, dev, target_devtype,
                        ret['linknets'], parsed_args['neighbors'], mlag_peer_dev)
                    ret['neighbors_compatible'] = True
                else:
                    ret['neighbors_compatible'] = False
                    ret['neighbors_error'] = "No linknets found"
            except (ValueError, cnaas_nms.confpush.init_device.InitVerificationError) as e:
                ret['neighbors_compatible'] = False
                ret['neighbors_error'] = str(e)
            except Exception as e:
                return empty_result(
                    status='error',
                    data="Exception in pre_init_check_neighbors: {}".format(e)), 500

            if mlag_peer_dev:
                try:
                    ret['mlag_compatible'] = mlag_peer_dev.hostname in ret['neighbors']
                except Exception:
                    ret['mlag_compatible'] = False

        ret['parsed_args'] = parsed_args
        if mlag_peer_id and not ret['mlag_compatible']:
            ret['compatible'] = False
        if ret['linknets_compatible'] and ret['neighbors_compatible']:
            ret['compatible'] = True
        else:
            ret['compatible'] = False
        return empty_result(data=ret)


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
            ztp_mac=ztp_mac, dhcp_ip=dhcp_ip, iteration=1,
            scheduled_by=get_jwt_identity())

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
        # default args
        kwargs: dict = {
            'dry_run': True,
            'auto_push': False,
            'force': False,
            'resync': False
        }

        if 'dry_run' in json_data and isinstance(json_data['dry_run'], bool) \
                and not json_data['dry_run']:
            kwargs['dry_run'] = False
        if 'force' in json_data and isinstance(json_data['force'], bool):
            kwargs['force'] = json_data['force']
        if 'auto_push' in json_data and isinstance(json_data['auto_push'], bool):
            kwargs['auto_push'] = json_data['auto_push']
        if 'resync' in json_data and isinstance(json_data['resync'], bool):
            kwargs['resync'] = json_data['resync']
        if 'comment' in json_data and isinstance(json_data['comment'], str):
            kwargs['job_comment'] = json_data['comment']
        if 'ticket_ref' in json_data and isinstance(json_data['ticket_ref'], str):
            kwargs['job_ticket_ref'] = json_data['ticket_ref']

        total_count: Optional[int] = None
        nr = cnaas_init()

        if 'hostname' in json_data:
            hostname = str(json_data['hostname'])
            if not Device.valid_hostname(hostname):
                return empty_result(
                    status='error',
                    data=f"Hostname '{hostname}' is not a valid hostname"
                ), 400
            _, total_count, _ = inventory_selector(nr, hostname=hostname)
            if total_count != 1:
                return empty_result(
                    status='error',
                    data=f"Hostname '{hostname}' not found or is not a managed device"
                ), 400
            kwargs['hostnames'] = [hostname]
            what = hostname
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
            _, total_count, _ = inventory_selector(nr, resync=kwargs['resync'],
                                                   device_type=devtype_str)
        elif 'group' in json_data:
            group_name = str(json_data['group'])
            if group_name not in get_groups():
                return empty_result(status='error', data='Could not find a group with name {}'.format(group_name))
            kwargs['group'] = group_name
            what = 'group {}'.format(group_name)
            _, total_count, _ = inventory_selector(nr, resync=kwargs['resync'],
                                                   group=group_name)
        elif 'all' in json_data and isinstance(json_data['all'], bool) and json_data['all']:
            what = "all devices"
            _, total_count, _ = inventory_selector(nr, resync=kwargs['resync'])
        else:
            return empty_result(
                status='error',
                data=f"No devices to synchronize were specified"
            ), 400

        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.confpush.sync_devices:sync_devices',
            when=1,
            scheduled_by=get_jwt_identity(),
            kwargs=kwargs)

        res = empty_result(data=f"Scheduled job to synchronize {what}")
        res['job_id'] = job_id

        resp = make_response(json.dumps(res), 200)
        if total_count:
            resp.headers['X-Total-Count'] = total_count
        resp.headers['Content-Type'] = "application/json"
        return resp


class DeviceUpdateFactsApi(Resource):
    @jwt_required
    @device_update_facts_api.expect(device_update_facts_model)
    def post(self):
        """ Start update facts of device(s) """
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
                dev: Device = session.query(Device). \
                    filter(Device.hostname == hostname).one_or_none()
                if not dev or (dev.state != DeviceState.MANAGED and
                               dev.state != DeviceState.UNMANAGED):
                    return empty_result(
                        status='error',
                        data=f"Hostname '{hostname}' not found or is in invalid state"
                    ), 400
            kwargs['hostname'] = hostname
            total_count = 1
        else:
            return empty_result(
                status='error',
                data="No target to be updated was specified"
            ), 400

        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.confpush.update:update_facts',
            when=1,
            scheduled_by=get_jwt_identity(),
            kwargs=kwargs)

        res = empty_result(data=f"Scheduled job to update facts for {hostname}")
        res['job_id'] = job_id

        resp = make_response(json.dumps(res), 200)
        if total_count:
            resp.headers['X-Total-Count'] = total_count
        resp.headers['Content-Type'] = "application/json"
        return resp


class DeviceUpdateInterfacesApi(Resource):
    @jwt_required
    @device_update_interfaces_api.expect(device_update_interfaces_model)
    def post(self):
        """Update/scan interfaces of device"""
        json_data = request.get_json()
        kwargs: dict = {
            "replace": False,
            "delete_all": False,
            "mlag_peer_hostname": None
        }

        total_count: Optional[int] = None

        if 'hostname' in json_data:
            hostname = str(json_data['hostname'])
            if not Device.valid_hostname(hostname):
                return empty_result(
                    status='error',
                    data=f"Hostname '{hostname}' is not a valid hostname"
                ), 400
            with sqla_session() as session:
                dev: Device = session.query(Device). \
                    filter(Device.hostname == hostname).one_or_none()
                if not dev or (dev.state != DeviceState.MANAGED and
                               dev.state != DeviceState.UNMANAGED):
                    return empty_result(
                        status='error',
                        data=f"Hostname '{hostname}' not found or is in invalid state"
                    ), 400
                if dev.device_type != DeviceType.ACCESS:
                    return empty_result(
                        status='error',
                        data=f"Only devices of type ACCESS has interface database to update"
                    ), 400
            kwargs['hostname'] = hostname
            total_count = 1
        else:
            return empty_result(
                status='error',
                data="No target to be updated was specified"
            ), 400

        if 'mlag_peer_hostname' in json_data:
            mlag_peer_hostname = str(json_data['mlag_peer_hostname'])
            if not Device.valid_hostname(mlag_peer_hostname):
                return empty_result(
                    status='error',
                    data=f"Hostname '{mlag_peer_hostname}' is not a valid hostname"
                ), 400
            with sqla_session() as session:
                dev: Device = session.query(Device). \
                    filter(Device.hostname == mlag_peer_hostname).one_or_none()
                if not dev or (dev.state != DeviceState.MANAGED and
                               dev.state != DeviceState.UNMANAGED):
                    return empty_result(
                        status='error',
                        data=f"Hostname '{mlag_peer_hostname}' not found or is in invalid state"
                    ), 400
                if dev.device_type != DeviceType.ACCESS:
                    return empty_result(
                        status='error',
                        data=f"Only devices of type ACCESS has interface database to update"
                    ), 400
            kwargs['mlag_peer_hostname'] = mlag_peer_hostname

        if 'replace' in json_data and isinstance(json_data['replace'], bool) \
                and json_data['replace']:
            kwargs['replace'] = True

        if 'delete_all' in json_data and isinstance(json_data['delete_all'], bool) \
                and json_data['delete_all']:
            kwargs['delete_all'] = True

        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.confpush.update:update_interfacedb',
            when=1,
            scheduled_by=get_jwt_identity(),
            kwargs=kwargs)

        res = empty_result(data=f"Scheduled job to update interfaces for {hostname}")
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
            template_vars['host'] = hostname
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


class DevicePreviousConfigApi(Resource):
    @jwt_required
    @device_api.param('job_id')
    @device_api.param('previous')
    @device_api.param('before')
    def get(self, hostname: str):
        args = request.args
        result = empty_result()
        result['data'] = {'config': None}
        if not Device.valid_hostname(hostname):
            return empty_result(
                status='error',
                data=f"Invalid hostname specified"
            ), 400

        kwargs = {}
        if 'job_id' in args:
            try:
                kwargs['job_id'] = int(args['job_id'])
            except Exception:
                return empty_result('error', "job_id must be an integer"), 400
        elif 'previous' in args:
            try:
                kwargs['previous'] = int(args['previous'])
            except Exception:
                return empty_result('error', "previous must be an integer"), 400
        elif 'before' in args:
            try:
                kwargs['before'] = datetime.datetime.fromisoformat(args['before'])
            except Exception:
                return empty_result('error', "before must be a valid ISO format date time string"), 400

        with sqla_session() as session:
            try:
                result['data'] = Job.get_previous_config(session, hostname, **kwargs)
            except JobNotFoundError as e:
                return empty_result('error', str(e)), 404
            except InvalidJobError as e:
                return empty_result('error', str(e)), 500
            except Exception as e:
                return empty_result('error', "Unhandled exception: {}".format(e)), 500

        return result

    @jwt_required
    @device_api.expect(device_restore_model)
    def post(self, hostname: str):
        """Restore configuration to previous version"""
        json_data = request.get_json()
        apply_kwargs = {'hostname': hostname}
        config = None
        if not Device.valid_hostname(hostname):
            return empty_result(
                status='error',
                data=f"Invalid hostname specified"
            ), 400

        if 'job_id' in json_data:
            try:
                job_id = int(json_data['job_id'])
            except Exception:
                return empty_result('error', "job_id must be an integer"), 400
        else:
            return empty_result('error', "job_id must be specified"), 400

        with sqla_session() as session:
            try:
                prev_config_result = Job.get_previous_config(session, hostname, job_id=job_id)
                failed = prev_config_result['failed']
                if not failed and 'config' in prev_config_result:
                    config = prev_config_result['config']
            except JobNotFoundError as e:
                return empty_result('error', str(e)), 404
            except InvalidJobError as e:
                return empty_result('error', str(e)), 500
            except Exception as e:
                return empty_result('error', "Unhandled exception: {}".format(e)), 500

        if failed:
            return empty_result('error', "The specified job_id has a failed status"), 400

        if not config:
            return empty_result('error', "No config found in this job"), 500

        if 'dry_run' in json_data and isinstance(json_data['dry_run'], bool) \
                and not json_data['dry_run']:
            apply_kwargs['dry_run'] = False
        else:
            apply_kwargs['dry_run'] = True

        apply_kwargs['config'] = config

        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.confpush.sync_devices:apply_config',
            when=1,
            scheduled_by=get_jwt_identity(),
            kwargs=apply_kwargs,
        )

        res = empty_result(data=f"Scheduled job to restore {hostname}")
        res['job_id'] = job_id

        return res, 200


class DeviceApplyConfigApi(Resource):
    @jwt_required
    @device_api.expect(device_apply_config_model)
    def post(self, hostname: str):
        """Apply exact specified configuration to device without using templates"""
        json_data = request.get_json()
        apply_kwargs = {'hostname': hostname}
        allow_live_run = get_apidata()['allow_apply_config_liverun']
        if not Device.valid_hostname(hostname):
            return empty_result(
                status='error',
                data=f"Invalid hostname specified"
            ), 400

        if 'full_config' not in json_data:
            return empty_result('error', "full_config must be specified"), 400

        if 'dry_run' in json_data and isinstance(json_data['dry_run'], bool) \
                and not json_data['dry_run']:
            if allow_live_run:
                apply_kwargs['dry_run'] = False
            else:
                return empty_result('error', "Apply config live_run is not allowed"), 400
        else:
            apply_kwargs['dry_run'] = True

        apply_kwargs['config'] = json_data['full_config']

        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.confpush.sync_devices:apply_config',
            when=1,
            scheduled_by=get_jwt_identity(),
            kwargs=apply_kwargs,
        )

        res = empty_result(data=f"Scheduled job to apply config {hostname}")
        res['job_id'] = job_id

        return res, 200


class DeviceCertApi(Resource):
    @jwt_required
    @device_api.expect(device_cert_model)
    def post(self):
        """Execute certificate related actions on device"""
        json_data = request.get_json()
        # default args
        kwargs: dict = {}

        if 'action' in json_data and isinstance(json_data['action'], str):
            action = json_data['action'].upper()
        else:
            return empty_result(
                status='error',
                data=f"Required field 'action' was not specified"
            ), 400

        if 'comment' in json_data and isinstance(json_data['comment'], str):
            kwargs['job_comment'] = json_data['comment']
        if 'ticket_ref' in json_data and isinstance(json_data['ticket_ref'], str):
            kwargs['job_ticket_ref'] = json_data['ticket_ref']

        total_count: Optional[int] = None
        nr = cnaas_init()

        if 'hostname' in json_data:
            hostname = str(json_data['hostname'])
            if not Device.valid_hostname(hostname):
                return empty_result(
                    status='error',
                    data=f"Hostname '{hostname}' is not a valid hostname"
                ), 400
            _, total_count, _ = inventory_selector(nr, hostname=hostname)
            if total_count != 1:
                return empty_result(
                    status='error',
                    data=f"Hostname '{hostname}' not found or is not a managed device"
                ), 400
            kwargs['hostname'] = hostname
        elif 'group' in json_data:
            group_name = str(json_data['group'])
            if group_name not in get_groups():
                return empty_result(status='error', data='Could not find a group with name {}'.format(group_name))
            kwargs['group'] = group_name
            _, total_count, _ = inventory_selector(nr, group=group_name)
        else:
            return empty_result(
                status='error',
                data=f"No devices were specified"
            ), 400

        if action == 'RENEW':
            scheduler = Scheduler()
            job_id = scheduler.add_onetime_job(
                'cnaas_nms.confpush.cert:renew_cert',
                when=1,
                scheduled_by=get_jwt_identity(),
                kwargs=kwargs)

            res = empty_result(data=f"Scheduled job to renew certificates")
            res['job_id'] = job_id

            resp = make_response(json.dumps(res), 200)
            if total_count:
                resp.headers['X-Total-Count'] = total_count
            resp.headers['Content-Type'] = "application/json"
            return resp
        else:
            return empty_result(
                status='error',
                data=f"Unknown action specified: {action}"
            ), 400


# Devices
device_api.add_resource(DeviceByIdApi, '/<int:device_id>')
device_api.add_resource(DeviceByHostnameApi, '/<string:hostname>')
device_api.add_resource(DeviceConfigApi, '/<string:hostname>/generate_config')
device_api.add_resource(DevicePreviousConfigApi, '/<string:hostname>/previous_config')
device_api.add_resource(DeviceApplyConfigApi, '/<string:hostname>/apply_config')
device_api.add_resource(DeviceApi, '')
devices_api.add_resource(DevicesApi, '')
device_init_api.add_resource(DeviceInitApi, '/<int:device_id>')
device_initcheck_api.add_resource(DeviceInitCheckApi, '/<int:device_id>')
device_discover_api.add_resource(DeviceDiscoverApi, '')
device_syncto_api.add_resource(DeviceSyncApi, '')
device_update_facts_api.add_resource(DeviceUpdateFactsApi, '')
device_update_interfaces_api.add_resource(DeviceUpdateInterfacesApi, '')
device_cert_api.add_resource(DeviceCertApi, '')
# device/<string:hostname>/current_config
