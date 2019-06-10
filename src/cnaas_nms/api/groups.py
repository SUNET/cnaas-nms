from flask import request
from flask_restful import Resource

from cnaas_nms.db.session import sqla_session, sqla_execute
from cnaas_nms.api.generic import empty_result
from cnaas_nms.api.generic import build_filter, empty_result
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.groups import Groups, DeviceGroups


class GroupsApi(Resource):
    def get(self):
        result = empty_result()
        result['groups'] = {'groups': Groups.group_get()}
        return empty_result(status='success', data=result)


class GroupsApiById(Resource):
    def get(self, group_name):
        result = empty_result()
        groups = Groups.group_get(index=0, name=group_name)
        if groups == []:
            return empty_result(status='error', data='Can not find group'), 404
        result['data'] = {'groups': groups}
        return empty_result(status='success', data=result)


class DeviceGroupsApi(Resource):
    def get(self, group_name):
        result = empty_result()
        result['data'] = {'groups': []}
        with sqla_session() as session:
            for row in session.query(Device, Groups).filter(DeviceGroups.device_id ==
                                                            Device.id, DeviceGroups.groups_id ==
                                                            Groups.id).filter(Groups.name ==
                                                                              group_name):
                result['data']['groups'].append(row.Device.id)
                result['data']['groups'].append(row.Device.hostname)
        return empty_result(status='success', data=result)
