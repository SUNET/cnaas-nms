from cnaas_nms.api.generic import build_filter, empty_result
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.user import User

from flask_restful import Resource
from flask import request


class AuthApi(Resource):
    def _validate_args(sef, args):
        if 'username' not in args:
            return -1
        if 'password' not in args:
            return -1
        if args['username'] is '':
            return -1
        if args['password'] is '':
            return -1
        return 0

    def _validate_credential(self, credential, args):
        if not credential:
            return empty_result(status='error', data='User not found'), 404
        if credential.active == False:
            return empty_result(status='error', data='Account disabled'), 404
        if credential.password != args['password']:
            return empty_result(status='error', data='Invalid password'), 404
        response = {'attributes': credential.attributes}
        return empty_result(status='success', data=response)

    def get(self):
        results = []
        args = request.args
        if self._validate_args(args) is -1:
            return empty_result(status='error', data='Malformed input'), 404
        with sqla_session() as session:
            username: User = session.query(User).filter(User.username ==
                                                        args['username']).one_or_none()
            return self._validate_credential(username, args)
        return empty_result(status='error', data='Authentication denied'), 404

    def post(self):
        json_data = request.get_json()
        if self._validate_args(json_data) is -1:
            return empty_result(status='error', data='Malformed input'), 404
        with sqla_session() as session:
            instance: User = session.query(User).filter(User.username ==
                                                        json_data['username']).one_or_none()
            if instance != None:
                return empty_result(status='error', data='User already exists')
            new_user = User()
            new_user.username = json_data['username']
            new_user.password = json_data['password']
            new_user.attributes = json_data['attributes']
            if 'description' in json_data:
                new_user.description = json_data['description']
            if 'attributes' in json_data:
                new_user.attributes = json_data['attributes']
            new_user.active = False
            session.add(new_user)
        return empty_result(status='success')
