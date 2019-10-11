from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required

from cnaas_nms.api.generic import empty_result
from cnaas_nms.plugins.pluginmanager import PluginManagerHandler


class PluginsApi(Resource):
    @jwt_required
    def get(self):
        try:
            pmh = PluginManagerHandler()
            plugindata = pmh.get_plugindata()
            plugin_module_names = pmh.get_plugins()
        except Exception as e:
            return empty_result('error', "Error retrieving plugins {}".
                                format(str(e)))
        else:
            return empty_result('success', {'loaded_plugins': plugin_module_names,
                                            'plugindata': plugindata})

    @jwt_required
    def put(self):
        json_data = request.get_json()
        if 'action' in json_data:
            if str(json_data['action']).upper() == 'SELFTEST':
                pmh = PluginManagerHandler()
                res = pmh.pm.hook.selftest()
                return empty_result('success', {'result': res})
            else:
                return empty_result('error', "Unknown action specified"), 400
        else:
            return empty_result('error', "No action specified"), 400

