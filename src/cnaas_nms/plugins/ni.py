import requests

from cnaas_nms.plugins.pluginspec import CnaasBasePlugin, hookimpl
from cnaas_nms.tools.log import get_logger

logger = get_logger()


class Plugin(CnaasBasePlugin):
    def __init__(self):
        self.urlbase = None
        self.apiuser = None
        self.apitoken = None

        pluginvars = self.get_vars(__name__)

        if "urlbase" in pluginvars:
            self.urlbase = pluginvars["urlbase"]
        if "apiuser" in pluginvars:
            self.apiuser = pluginvars["apiuser"]
        if "apitoken" in pluginvars:
            self.apitoken = pluginvars["apitoken"]

    @hookimpl
    def selftest(self):
        if self.urlbase and self.apiuser and self.apitoken:
            return True
        else:
            return False

    @hookimpl
    def new_managed_device(self, hostname, device_type, serial_number, vendor, model, os_version, management_ip):
        headers = {"Authorization": "ApiKey {}:{}".format(self.apiuser, self.apitoken)}

        data = {"node": {"operational_state": "In service"}}

        res = requests.get(self.urlbase, headers=headers, verify=False)  # noqa: S501
        if not res.status_code == 200:
            logger.warning("Failed to fetch devices from NI: {}: {} ({})".format(res.status_code, res.text, data))

            return False

        for device in res.json()["objects"]:
            if device["node_name"] != hostname:
                continue

            if management_ip:
                if "ip_addresses" in device["node"]:
                    addresses = device["node"]["ip_addresses"]
                    data["node"]["ip_addresses"] = addresses
                    data["node"]["ip_addresses"].insert(0, management_ip)
                else:
                    data["node"]["ip_addresses"] = [management_ip]

            handle_id = device["handle_id"]
            res = requests.put(
                self.urlbase + str(handle_id) + "/", headers=headers, json=data, verify=False  # noqa: S501
            )

            if res.status_code != 204:
                logger.warning("Could not change device {} with ID {}.".format(hostname, handle_id))
                return False
