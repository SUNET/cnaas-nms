from nornir import InitNornir

from nornir.core.deserializer.inventory import Inventory
from nornir.core.filter import F

from nornir.plugins.tasks import networking, text
from nornir.plugins.functions.text import print_title, print_result

import cnaas_nms.confpush.nornir_helper
from cnaas_nms.cmdb.session import session_scope
from cnaas_nms.cmdb.device import Device

import datetime

def push_base_management(task):
    template_vars = {
        'uplinks': [{'ifname': 'Ethernet2'}],
        'mgmt_vlan_id': 600,
        'mgmt_ip': '10.0.6.10/24',
        'mgmt_gw': '10.0.6.1'
    }

    r = task.run(task=text.template_file,
                 name="Base management",
                 template="managed-base.j2",
                 path=f"../templates/{task.host.platform}",
                 **template_vars)

    task.host["config"] = r.result

    task.run(task=networking.napalm_configure,
             name="Push base management config",
             replace=False,
             configuration=task.host["config"])

def init_access_device(hostname=None):
    """Get neighbor information from device

    Args:
        hostname (str): Optional hostname of device to query

    Returns:
        Nornir result object
    """
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname)

    result = nr_filtered.run(task=push_base_management)

    print_result(result)

    return result

