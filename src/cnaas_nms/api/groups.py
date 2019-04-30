from flask import request
from flask_restful import Resource

from cnaas_nms.db.session import sqla_session
from cnaas_nms.api.generic import empty_result
from cnaas_nms.api.device import DeviceValidate
from cnaas_nms.api.generic import build_filter, empty_result
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.groups import Groups

class GroupsApi(Resource):        
    def get(self):
        data = {}
        result = []
        json_data = request.get_json()
        with sqla_session() as session:
            query = session.query(Groups)
            query = build_filter(Groups, query)
            for instance in query:
                result.append(instance.as_dict())
        return empty_result(status='success', data=result)

    def post(self):
        json_data = request.get_json()
        if json_data == None:
            return empty_result(status='error', data='JSON data must not be empty'), 200
        with sqla_session() as session:
            instance: Groups = session.query(Groups).filter(Groups.name == json_data['name']).one_or_none()
            if instance != None:
                errors.append('Group already exists')
                return errors
            new_group = Groups()
            # We shoule probbay have some validation of the name here,
            # but let's do that later.
            new_group.name = json_data['name']
            new_group.description = json_data['description']
            session.add(new_group)
        return empty_result(status='success'), 200

        
class GroupsApiByName(Resource):
    def get(self, group_id):
        result = empty_result()
        result['data'] = {'groups': []}
        with sqla_session() as session:
            instance = session.query(Groups).filter(Groups.id == group_id).one_or_none()
            if instance:
                result['data']['groups'].append(instance.as_dict())
            else:
                return empty_result('error', "Device not found"), 404
        return result

    def put(self, group_id):
        errors = []
        json_data = request.get_json()
        if json_data == None:
            return empty_result(status='error', data='JSON data must not be empty'), 200
        with sqla_session() as session:
            instance: Groups = session.query(Groups).filter(Groups.id == group_id).one_or_none()
            if instance:
                if 'name' in json_data:
                    instance.name = json_data['name']
                if 'description' in json_data:
                    instance.description = json_data['description']
            else:
                errors.append('Group not found')
        if errors != []:
            return empty_result(status='error', data=errors), 404
        return empty_result(status='success'), 200

    def delete(self, group_id):
        with sqla_session() as session:
            instance = session.query(Groups).filter(Groups.id == group_id).one_or_none()
            if instance:
                session.delete(instance)
                session.commit()
                return empty_result(), 200
            else:
                return empty_result('error', "Group not found"), 404

