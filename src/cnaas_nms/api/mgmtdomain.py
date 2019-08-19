from flask import request
from flask_restful import Resource
from ipaddress import IPv4Interface

from cnaas_nms.api.generic import build_filter, empty_result, limit_results
from cnaas_nms.db.device import Device
from cnaas_nms.db.mgmtdomain import Mgmtdomain
from cnaas_nms.db.session import sqla_session


class MgmtdomainByIdApi(Resource):
    def get(self, mgmtdomain_id):
        result = empty_result()
        result['data'] = {'mgmtdomains': []}
        with sqla_session() as session:
            instance = session.query(Mgmtdomain).\
                filter(Mgmtdomain.id == mgmtdomain_id).one_or_none()
            if instance:
                result['data']['mgmtdomains'].append(instance.as_dict())
            else:
                return empty_result('error', "Management domain not found"), 404
        return result

    def delete(self, mgmtdomain_id):
        with sqla_session() as session:
            instance = session.query(Mgmtdomain).\
                filter(Mgmtdomain.id == mgmtdomain_id).one_or_none()
            if instance:
                session.delete(instance)
                session.commit()
                return empty_result(), 204
            else:
                return empty_result('error', "Management domain not found"), 404

    def put(self, mgmtdomain_id):
        json_data = request.get_json()
        data = {}
        errors = []
        if 'vlan' in json_data:
            try:
                vlan_id_int = int(json_data['vlan'])
            except:
                errors.append('Invalid VLAN received.')
            else:
                data['vlan'] = vlan_id_int
        if 'ipv4_gw' in json_data:
            try:
                addr = IPv4Interface(json_data['ipv4_gw'])
                prefix_len = int(addr.network.prefixlen)
            except:
                errors.append('Invalid ipv4_gw received. Must be correct IPv4 address with mask')
            else:
                if prefix_len <= 31 and prefix_len >= 16:
                    data['ipv4_gw'] = str(addr)
                else:
                    errors.append("Bad prefix length for management network: {}".format(
                        prefix_len))
        with sqla_session() as session:
            instance = session.query(Mgmtdomain).filter(Mgmtdomain.id == mgmtdomain_id).one_or_none()
            if instance:
                #TODO: auto loop through class members and match
                if 'vlan' in data:
                    instance.vlan = data['vlan']
                if 'ipv4_gw' in data:
                    instance.ipv4_gw = data['ipv4_gw']


class MgmtdomainsApi(Resource):
    def get(self):
        result = empty_result()
        result['data'] = {'mgmtdomains': []}
        filter_exp = None
        with sqla_session() as session:
            query = session.query(Mgmtdomain)
            query = build_filter(Mgmtdomain, query).limit(limit_results())
            for instance in query:
                result['data']['mgmtdomains'].append(instance.as_dict())
        return result

    def post(self):
        json_data = request.get_json()
        data = {}
        errors = []

        with sqla_session() as session:
            if 'device_a_id' in json_data:
                try:
                    device_a_id = int(json_data['device_a_id'])
                except Exception:
                    errors.appemnd('Invalid device ID for device_a_id')
                else:
                    device_a_db = session.query(Device).\
                        filter(Device.id == device_a_id).one_or_none()
                    if not device_a_db:
                        errors.append(f"Device with ID {device_a_id} not found")
                    else:
                        data['device_a_id'] = device_a_id
            if 'device_b_id' in json_data:
                try:
                    device_b_id = int(json_data['device_b_id'])
                except Exception:
                    errors.appemnd('Invalid device ID for device_b_id')
                else:
                    device_b_db = session.query(Device).\
                        filter(Device.id == device_b_id).one_or_none()
                    if not device_b_db:
                        errors.append(f"Device with ID {device_b_id} not found")
                    else:
                        data['device_b_id'] = device_b_id
            if 'vlan' in json_data:
                try:
                    vlan_id_int = int(json_data['vlan'])
                except:
                    errors.append('Invalid VLAN received.')
                else:
                    data['vlan'] = vlan_id_int
            if 'ipv4_gw' in json_data:
                try:
                    addr = IPv4Interface(json_data['ipv4_gw'])
                    prefix_len = int(addr.network.prefixlen)
                except:
                    errors.append(('Invalid ipv4_gw received. '
                                   'Must be correct IPv4 address with mask'))
                else:
                    if prefix_len <= 31 and prefix_len >= 16:
                        data['ipv4_gw'] = str(addr)
                    else:
                        errors.append("Bad prefix length for management network: {}".format(
                            prefix_len))
            required_keys = ['device_a_id', 'device_b_id', 'vlan', 'ipv4_gw']
            if all([key in data for key in required_keys]):
                new_mgmtd = Mgmtdomain()
                new_mgmtd.device_a_id = data['device_a_id']
                new_mgmtd.device_b_id = data['device_b_id']
                new_mgmtd.ipv4_gw = data['ipv4_gw']
                new_mgmtd.vlan = data['vlan']
                result = session.add(new_mgmtd)
                return empty_result(), 200
            else:
                errors.append("Not all required inputs were found: {}".\
                              format(', '.join(required_keys)))
                return empty_result('error', errors), 400
