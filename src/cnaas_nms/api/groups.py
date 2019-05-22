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

    def post(self):
        json_data = request.get_json()
        if json_data is None:
            return empty_result(status='error',
                                data='JSON data must not be empty'), 404
        if 'name' not in json_data:
            return empty_result(status='error', data='Missing group name'), 404
        if 'description' not in json_data:
            json_data['description'] = ''
        result = Groups.group_add(json_data['name'], json_data['description'])
        if result != []:
            return empty_result(status='error', data=result), 404
        return empty_result(status='success'), 200


class GroupsApiById(Resource):
    def get(self, group_name):
        result = empty_result()
        groups = Groups.group_get(index=0, name=group_name)
        if groups == []:
            return empty_result(status='error', data='Can not find group'), 404
        result['data'] = {'groups': groups}
        return empty_result(status='success', data=result)

    def put(self, group_name):
        errors = []
        json_data = request.get_json()
        if json_data is None:
            return empty_result(status='error',
                                data='JSON data must not be empty'), 200
        if 'description' not in json_data:
            json_data['description'] = ''
        errors = Groups.group_update(group_name,
                                     json_data['description'])
        if errors != None:
            return empty_result(status='error', data=errors), 404
        return empty_result(status='success'), 200

    def delete(self, group_name):
        with sqla_session() as session:
            instance: Groups = session.query(Groups).filter(Groups.name ==
                                                    group_name).one_or_none()
            if instance:
                session.delete(instance)
                session.commit()
                return empty_result(), 200
        return empty_result('error', 'Group not found'), 404


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

    def post(self, group_name):
        json_data = request.get_json()
        if 'id' not in json_data:
            return empty_result(status='error', data='Device ID not found')
        result = Device.device_group_add(group_name, json_data['id'])
        if result is not None:
            return empty_result(status='error', data=result), 404
        return empty_result(status='success'), 200


class DeviceGroupsApiById(Resource):
    def delete(self, group_name, device_id):
        with sqla_session() as session:
            instance: Groups = session.query(Groups).filter(Groups.name ==
                                                            group_name).one_or_none()
            if not instance:
                return empty_result(status='error', data='Could not find group'), 404
            group = (instance.as_dict())
            instance: Device = session.query(Device).filter(Device.id ==
                                                            device_id).one_or_none()
            if not instance:
                return empty_result(status='error', data='Could not find device'), 404
            device = (instance.as_dict())
            instance: DeviceGroups = session.query(DeviceGroups).filter(DeviceGroups.device_id ==
                                                                        device['id'],
                                                                        DeviceGroups.groups_id ==
                                                                        group['id']).one_or_none()
            if not instance:
                return empty_result(status='error', data='Couöd not find matching device and group IDs'), 404
            session.delete(instance)
            session.commit()
        return empty_result(status='success'), 200

    def get(self, group_name, device_id):
        with sqla_session() as session:
            instance: Device = session.query(Device).filter(Device.id ==
                                                            device_id).one_or_none()
            if not instance:
                return empty_result(status='error', data='Can not find device'), 404
        return empty_result(status='success', data=instance.as_dict())
