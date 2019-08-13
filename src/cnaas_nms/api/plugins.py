from flask_restful import Resource

from cnaas_nms.api.generic import empty_result
from cnaas_nms.plugins.pluginmanager import PluginManagerHandler


class PluginsApi(Resource):
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

    def put(self):
        # run selftest
        pass
#        json_data = request.get_json()
        pmh = PluginManagerHandler()
        res = pmh.pm.hook.selftest()
        return empty_result('success', {'result': res})
#        return empty_result('error', "No action specified"), 400

