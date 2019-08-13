import yaml
import importlib

import pluggy

from cnaas_nms.plugins.pluginspec import CnaasPluginSpec
from cnaas_nms.tools.log import get_logger


logger = get_logger()


class PluginManager:
    def __init__(self):
        self.pm = pluggy.PluginManager("cnaas-nms")
        self.pm.add_hookspecs(CnaasPluginSpec)

    @classmethod
    def get_plugindata(cls, config='/etc/cnaas-nms/plugins.yml'):
        with open(config, 'r') as plugins_file:
            data = yaml.safe_load(plugins_file)
            if 'plugins' in data and isinstance(data['plugins'], list):
                return data
            else:
                logger.error("No plugins defined in plugins.yml")
                return None

    def load_plugins(self):
        plugindata = self.get_plugindata()
        if not plugindata:
            logger.error("Could not get plugins")
            return
        for plugin in plugindata['plugins']:
            if not 'filename':
                logger.error("Invalid plugin configuration: {}".format(plugin))
            try:
                module_name = "cnaas_nms.plugins." + plugin['filename'].rsplit('.',1)[0]
                pluginmodule = importlib.import_module(module_name)
            except Exception:
                logger.error("Could not load module {}".format(module_name))

            if not callable(pluginmodule.Plugin):
                logger.error("Could not find callable Plugin class in module {}".
                             format(module_name))
            else:
                self.pm.register(pluginmodule.Plugin())

        for res in self.pm.hook.selftest():
            if not res:
                logger.error("Plugin initialization selftest failed")
