import logging

import requests

from cnaas_nms.plugins.pluginspec import CnaasBasePlugin, hookimpl
from cnaas_nms.tools.log import get_logger

logger = get_logger()


class Plugin(CnaasBasePlugin):
    def __init__(self):
        self.urlbase = None
        self.apitoken = None
        self.organizationid = "Undefined"
        self.snmp_community = "public"
        self.roomid = "Undefined"
        pluginvars = self.get_vars(__name__)
        if 'urlbase' in pluginvars:
            self.urlbase = pluginvars['urlbase']
        if 'apitoken' in pluginvars:
            self.apitoken = pluginvars['apitoken']
        if 'organizationid' in pluginvars:
            self.organizationid= pluginvars['organizationid']
        if 'roomid' in pluginvars:
            self.roomid = pluginvars['roomid']
        if 'snmp_community' in pluginvars:
            self.snmp_community = pluginvars['snmp_community']

    @hookimpl
    def selftest(self):
        if self.urlbase and self.apitoken:
            return True
        else:
            return False

    @hookimpl
    def new_managed_device(self, hostname, device_type, serial_number, vendor,
                           model, os_version, management_ip):
        headers = {'Authorization': 'Token '+self.apitoken}
        data = {
            "ip": management_ip,
            "sysname": hostname,
            "roomid": self.roomid,
            "organizationid": self.organizationid,
            "categoryid": "SW",
            "snmp_version": 2,
            "read_only": self.snmp_community
        }
        r = requests.post(self.urlbase + "/api/1/netbox/",
                          headers=headers,
                          json=data)
        if not r.status_code == 201:
            logger.warn("Failed to add device to NAV: code {}: {} (data: {})".format(
                r.status_code, r.text, data
            ))
            return False
