from typing import List

from flask import request
from flask_restful import Resource

from cnaas_nms.api.generic import empty_result
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import Device
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.db.settings import get_settings


class InterfaceApi(Resource):
    def get(self, hostname):
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
                    intfdata = {}
                    intf: Interface = session.query(Interface).filter(Interface.device == dev).\
                        filter(Interface.name == if_name).one_or_none()
                    if not intf:
                        errors.append(f"Interface {if_name} not found")
                        continue

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
                        if 'vxlan' in if_dict['data']:
                            if not device_settings:
                                device_settings, _ = get_settings(hostname, dev.device_type)
                            if if_dict['data']['vxlan'] in device_settings['vxlans']:
                                intfdata['vxlan'] = if_dict['data']['vxlan']
                            else:
                                errors.append("Specified VXLAN {} is not present in {}".format(
                                    if_dict['data']['vxlan'], hostname
                                ))

                    if intfdata:
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

