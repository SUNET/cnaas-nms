import pluggy

import cnaas_nms.plugins.pluginmanager


hookspec = pluggy.HookspecMarker("cnaas-nms")
hookimpl = pluggy.HookimplMarker("cnaas-nms")


class CnaasPluginSpec(object):
    """Specification of CNaaS-NMS compatible plugins."""

    @hookspec
    def selftest(self):
        """Test that plugin can connect to it's API etc."""


class CnaasBasePlugin(object):
    def get_vars(self, module_name=None):
        data = cnaas_nms.plugins.pluginmanager.PluginManager.get_plugindata()
        plugin_name = module_name.split('.')[-1]
        for plugin in data['plugins']:
            if plugin['filename'].rsplit('.',1)[0] == plugin_name:
                if 'vars' in plugin:
                    return plugin['vars']
