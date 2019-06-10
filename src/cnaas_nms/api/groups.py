from flask_restful import Resource

from cnaas_nms.db.device import Device
from cnaas_nms.api.generic import empty_result
from cnaas_nms.db.settings import get_groups


def groups_populate(group_name=''):
    tmpgroups = dict()
    devices = Device.device_get()
    for _ in devices:
        groups = get_groups(_['hostname'])
        if groups == []:
            continue
        for group in groups:
            if group_name != '' and group != group_name:
                continue
            if group not in tmpgroups:
                tmpgroups[group] = []
            tmpgroups[group].append(_['hostname'])
    return tmpgroups


class GroupsApi(Resource):
    def get(self):
        result = empty_result()
        tmpgroups = groups_populate()
        result['data'] = {'groups': tmpgroups}
        return empty_result(status='success', data=result)


class GroupsApiById(Resource):
    def get(self, group_name):
        result = empty_result()
        tmpgroups = groups_populate(group_name)
        result['data'] = {'groups': tmpgroups}
        return empty_result(status='success', data=result)
