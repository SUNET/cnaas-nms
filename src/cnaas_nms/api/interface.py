from typing import List

from flask import request
from flask_restplus import Resource, Namespace, fields
from flask_jwt_extended import jwt_required

from cnaas_nms.api.generic import empty_result
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import Device
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.db.settings import get_settings
from cnaas_nms.version import __api_version__
from cnaas_nms.confpush.sync_devices import resolve_vlanid, resolve_vlanid_list


api = Namespace('device', description='API for handling interfaces',
                prefix='/api/{}'.format(__api_version__))


class InterfaceApi(Resource):
    @jwt_required
    def get(self, hostname):
        """ List all interfaces """
        result = empty_result()
        result['data'] = {'interfaces': []}
        with sqla_session() as session:
            dev = session.query(Device).filter(Device.hostname == hostname).one_or_none()
            if not dev:
                return empty_result('error', "Device not found"), 404
            result['data']['hostname'] = dev.hostname
            intfs = session.query(Interface).filter(Interface.device == dev).all()
            intf: Interface
            for intf in intfs:
                result['data']['interfaces'].append(intf.as_dict())
        return result

    @jwt_required
    def put(self, hostname):
        """Take a map of interfaces and associated values to update.
        Example:
            {"interfaces": {"Ethernet1": {"configtype": "ACCESS_AUTO"}}}
        """
        json_data = request.get_json()
        data = {}
        errors = []
        device_settings = None

        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
            if not dev:
                return empty_result('error', "Device not found"), 404

            updated = False
            if 'interfaces' in json_data and isinstance(json_data['interfaces'], dict):
                for if_name, if_dict in json_data['interfaces'].items():
                    if not isinstance(if_dict, dict):
                        errors.append("Each interface must have a dict with data to update")
                        continue
                    intf: Interface = session.query(Interface).filter(Interface.device == dev).\
                        filter(Interface.name == if_name).one_or_none()
                    if not intf:
                        errors.append(f"Interface {if_name} not found")
                        continue
                    if intf.data and isinstance(intf.data, dict):
                        intfdata_original = dict(intf.data)
                        intfdata = dict(intf.data)
                    else:
                        intfdata = {}

                    if 'configtype' in if_dict:
                        configtype = if_dict['configtype'].upper()
                        if InterfaceConfigType.has_name(configtype):
                            if intf.configtype != InterfaceConfigType[configtype]:
                                intf.configtype = InterfaceConfigType[configtype]
                                updated = True
                                data[if_name] = {'configtype': configtype}
                        else:
                            errors.append(f"Invalid configtype received: {configtype}")

                    if 'data' in if_dict:
                        # TODO: maybe this validation should be done via
                        #  pydantic if it gets more complex
                        if not device_settings:
                            device_settings, _ = get_settings(hostname, dev.device_type)
                        if 'vxlan' in if_dict['data']:
                            if if_dict['data']['vxlan'] in device_settings['vxlans']:
                                intfdata['vxlan'] = if_dict['data']['vxlan']
                            else:
                                errors.append("Specified VXLAN {} is not present in {}".format(
                                    if_dict['data']['vxlan'], hostname
                                ))
                        if 'untagged_vlan' in if_dict['data']:
                            vlan_id = resolve_vlanid(if_dict['data']['untagged_vlan'], device_settings['vxlans'])
                            if vlan_id:
                                intfdata['untagged_vlan'] = if_dict['data']['untagged_vlan']
                            else:
                                errors.append("Specified VLAN name {} is not present in {}".format(
                                    if_dict['data']['untagged_vlan'], hostname
                                ))
                        if 'tagged_vlan_list' in if_dict['data']:
                            if isinstance(if_dict['data']['tagged_vlan_list'], list):
                                vlan_id_list = resolve_vlanid_list(if_dict['data']['tagged_vlan_list'],
                                                                   device_settings['vxlans'])
                                if len(vlan_id_list) == len(if_dict['data']['tagged_vlan_list']):
                                    intfdata['tagged_vlan_list'] = if_dict['data']['tagged_vlan_list']
                                else:
                                    errors.append("Some VLAN names {} are not present in {}".format(
                                        ", ".join(if_dict['data']['tagged_vlan_list']), hostname
                                    ))
                            else:
                                errors.append("tagged_vlan_list should be of type list, found {}".format(
                                    type(if_dict['data']['tagged_vlan_list'])
                                ))
                        if 'neighbor' in if_dict['data']:
                            if isinstance(if_dict['data']['neighbor'], str) and \
                                    Device.valid_hostname(if_dict['data']['neighbor']):
                                intfdata['neighbor'] = if_dict['data']['neighbor']
                            else:
                                errors.append("Neighbor must be valid hostname, got: {}".format(
                                    if_dict['data']['neighbor']))
                        if 'description' in if_dict['data']:
                            if isinstance(if_dict['data']['description'], str) and \
                                    len(if_dict['data']['description']) <= 64:
                                if if_dict['data']['description']:
                                    intfdata['description'] = if_dict['data']['description']
                                elif 'description' in intfdata:
                                    del intfdata['description']
                            elif if_dict['data']['description'] is None:
                                if 'description' in intfdata:
                                    del intfdata['description']
                            else:
                                errors.append(
                                    "Description must be a string of 0-64 characters for: {}".
                                    format(if_dict['data']['description']))
                        if 'enabled' in if_dict['data']:
                            if type(if_dict['data']['enabled']) == bool:
                                intfdata['enabled'] = if_dict['data']['enabled']
                            else:
                                errors.append(
                                    "Enabled must be a bool, true or false, got: {}".
                                    format(if_dict['data']['enabled']))

                    if intfdata != intfdata_original:
                        intf.data = intfdata
                        updated = True
                        if if_name in data:
                            data[if_name]['data'] = intfdata
                        else:
                            data[if_name] = {'data': intfdata}

            if updated:
                dev.synchronized = False

        if errors:
            if data:
                ret = {'errors': errors, 'updated': data}
            else:
                ret = {'errors': errors}
            return empty_result(status='error', data=ret), 400
        else:
            return empty_result(status='success', data={'updated': data})


api.add_resource(InterfaceApi, '/<string:hostname>/interfaces')
