from flask import request
from flask_restx import Resource, Namespace, fields
from flask import make_response
from flask_jwt_extended import jwt_required

from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.settings import get_settings, check_settings_syntax, SettingsSyntaxError
from cnaas_nms.api.generic import empty_result
from cnaas_nms.version import __api_version__
from cnaas_nms.db.settings import get_settings_root
from cnaas_nms.tools.mergedict import merge_dict_origin


settings_root_model = get_settings_root()


api = Namespace('settings', description='Settings',
                prefix='/api/{}'.format(__api_version__))


class SettingsApi(Resource):
    @jwt_required()
    @api.param('hostname')
    @api.param('device_type')
    def get(self):
        """ Get settings """
        args = request.args
        hostname = None
        device_type = None
        model = None
        if 'hostname' in args:
            if Device.valid_hostname(args['hostname']):
                hostname = args['hostname']
            else:
                return empty_result('error', "Invalid hostname specified"), 400
            with sqla_session() as session:
                dev: Device = session.query(Device).\
                    filter(Device.hostname == hostname).one_or_none()
                if dev:
                    device_type = dev.device_type
                    model = dev.model
                else:
                    return empty_result('error', "Hostname not found in database"), 400
        if 'device_type' in args:
            if DeviceType.has_name(args['device_type'].upper()):
                device_type = DeviceType[args['device_type'].upper()]
            else:
                return empty_result('error', "Invalid device type specified"), 400

        try:
            settings, settings_origin = get_settings(hostname, device_type, model)
        except Exception as e:
            return empty_result('error', "Error getting settings: {}".format(str(e))), 400

        return empty_result(data={'settings': settings, 'settings_origin': settings_origin})


class SettingsModelApi(Resource):
    def get(self):
        response = make_response(settings_root_model.schema_json())
        response.headers['Content-Type'] = "application/json"
        return response

    def post(self):
        json_data = request.get_json()
        syntax_dict, syntax_dict_origin = merge_dict_origin({}, json_data, {}, 'API POST data')
        try:
            ret = check_settings_syntax(syntax_dict, syntax_dict_origin)
        except SettingsSyntaxError as e:
            return empty_result(status='error', data=str(e)), 400
        else:
            return empty_result(status='success', data=ret)


api.add_resource(SettingsApi, '')
api.add_resource(SettingsModelApi, '/model')
