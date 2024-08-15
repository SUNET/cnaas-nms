from flask import request
from flask_restx import Namespace, Resource, fields

from cnaas_nms.api.generic import empty_result
from cnaas_nms.plugins.pluginmanager import PluginManagerHandler
from cnaas_nms.tools.security import login_required
from cnaas_nms.version import __api_version__

api = Namespace("plugins", description="API for handling plugins", prefix="/api/{}".format(__api_version__))

plugin_model = api.model(
    "plugin",
    {
        "action": fields.String(required=True),
    },
)


class PluginsApi(Resource):
    @login_required
    def get(self):
        """List all plugins"""
        try:
            pmh = PluginManagerHandler()
            plugindata = pmh.get_plugindata()
            plugin_module_names = pmh.get_plugins()
        except Exception as e:
            return empty_result("error", "Error retrieving plugins {}".format(str(e)))
        else:
            return empty_result("success", {"loaded_plugins": plugin_module_names, "plugindata": plugindata})

    @login_required
    @api.expect(plugin_model)
    def put(self):
        """Modify plugins"""
        json_data = request.get_json()
        if "action" in json_data:
            if str(json_data["action"]).upper() == "SELFTEST":
                pmh = PluginManagerHandler()
                res = pmh.pm.hook.selftest()
                return empty_result("success", {"result": res})
            else:
                return empty_result("error", "Unknown action specified"), 400
        else:
            return empty_result("error", "No action specified"), 400


api.add_resource(PluginsApi, "")
