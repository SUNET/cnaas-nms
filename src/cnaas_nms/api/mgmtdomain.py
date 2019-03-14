
from flask import request
from flask_restful import Resource
from ipaddress import IPv4Interface

import cnaas_nms.confpush.init_device
from cnaas_nms.api.generic import build_filter, empty_result, limit_results
from cnaas_nms.cmdb.device import Device, DeviceState, DeviceType
from cnaas_nms.cmdb.mgmtdomain import Mgmtdomain
from cnaas_nms.cmdb.session import sqla_session
from cnaas_nms.scheduler.scheduler import Scheduler

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
            except:
                errors.append('Invalid ipv4_gw received. Must be correct IPv4 address with mask')
            else:
                data['ipv4_gw'] = str(addr)
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
