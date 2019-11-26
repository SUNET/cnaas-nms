from flask import request
from flask_restplus import Resource, Namespace, fields
from flask_jwt_extended import jwt_required

from ipaddress import IPv4Interface

from cnaas_nms.api.generic import build_filter, empty_result, limit_results
from cnaas_nms.db.device import Device
from cnaas_nms.db.mgmtdomain import Mgmtdomain
from cnaas_nms.db.session import sqla_session
from cnaas_nms.version import __api_version__


api = Namespace('mgmtdomains', description='API for handling managemeent domains',
                prefix='/api/{}'.format(__api_version__))

mgmtdomain_model = api.model('mgmtdomain', {
    'device_a': fields.String(required=True),
    'device_b': fields.String(required=True),
    'vlan': fields.Integer(required=True),
    'ipv4_gw': fields.String(required=True),
})


class MgmtdomainByIdApi(Resource):
    @jwt_required
    def get(self, mgmtdomain_id):
        """ Get management domain by ID """
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

    @jwt_required
    def delete(self, mgmtdomain_id):
        """ Remove management domain """
        with sqla_session() as session:
            instance = session.query(Mgmtdomain).\
                filter(Mgmtdomain.id == mgmtdomain_id).one_or_none()
            if instance:
                session.delete(instance)
                session.commit()
                return empty_result(), 204
            else:
                return empty_result('error', "Management domain not found"), 404

    @jwt_required
    @api.expect(mgmtdomain_model)
    def put(self, mgmtdomain_id):
        """ Modify management domain """
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
    @jwt_required
    def get(self):
        """ Get all management domains """
        result = empty_result()
        result['data'] = {'mgmtdomains': []}
        filter_exp = None
        with sqla_session() as session:
            query = session.query(Mgmtdomain)
            query = build_filter(Mgmtdomain, query).limit(limit_results())
            for instance in query:
                result['data']['mgmtdomains'].append(instance.as_dict())
        return result

    @jwt_required
    @api.expect(mgmtdomain_model)
    def post(self):
        """ Add management domain """
        json_data = request.get_json()
        data = {}
        errors = []
        with sqla_session() as session:
            if 'device_a' in json_data:
                hostname_a = str(json_data['device_a'])
                if not Device.valid_hostname(hostname_a):
                    errors.append(f"Invalid hostname for device_a: {hostname_a}")
                else:
                    device_a = session.query(Device).\
                        filter(Device.hostname == hostname_a).one_or_none()
                    if not device_a:
                        errors.append(f"Device with hostname {hostname_a} not found")
                    else:
                        data['device_a'] = device_a
            if 'device_b' in json_data:
                hostname_b = str(json_data['device_b'])
                if not Device.valid_hostname(hostname_b):
                    errors.append(f"Invalid hostname for device_b: {hostname_b}")
                else:
                    device_b = session.query(Device).\
                        filter(Device.hostname == hostname_b).one_or_none()
                    if not device_b:
                        errors.append(f"Device with hostname {hostname_b} not found")
                    else:
                        data['device_b'] = device_b
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
            required_keys = ['device_a', 'device_b', 'vlan', 'ipv4_gw']
            if all([key in data for key in required_keys]):
                new_mgmtd = Mgmtdomain()
                new_mgmtd.device_a = data['device_a']
                new_mgmtd.device_b = data['device_b']
                new_mgmtd.ipv4_gw = data['ipv4_gw']
                new_mgmtd.vlan = data['vlan']
                result = session.add(new_mgmtd)
                return empty_result(result, 200)
            else:
                errors.append("Not all required inputs were found: {}".\
                              format(', '.join(required_keys)))
                return empty_result('error', errors), 400


api.add_resource(MgmtdomainsApi, '')
api.add_resource(MgmtdomainByIdApi, '/<int:mgmtdomain_id>')
