import pluggy

import cnaas_nms.plugins.pluginmanager

hookspec = pluggy.HookspecMarker("cnaas-nms")
hookimpl = pluggy.HookimplMarker("cnaas-nms")


class CnaasPluginSpec(object):
    """Specification of CNaaS-NMS compatible plugins."""

    @hookspec
    def selftest(self):
        """Test that plugin can connect to it's API etc."""

    def allocated_ipv4(self, vrf, ipv4_address, ipv4_network, hostname):
        """A new IPv4 address has been allocated by CNaaS NMS"""

    def new_managed_device(self, hostname, device_type, serial_number, vendor, model, os_version, management_ip):
        """A new managed device has been added, or a device has become managed."""


class CnaasBasePlugin(object):
    @classmethod
    def get_vars(cls, module_name=None):
        data = cnaas_nms.plugins.pluginmanager.PluginManagerHandler.get_plugindata()
        plugin_name = module_name.split(".")[-1]
        for plugin in data["plugins"]:
            if plugin["filename"].rsplit(".", 1)[0] == plugin_name:
                if "vars" in plugin:
                    return plugin["vars"]
