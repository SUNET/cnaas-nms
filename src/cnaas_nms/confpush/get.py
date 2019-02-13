from nornir import InitNornir

from nornir.core.deserializer.inventory import Inventory
from nornir.core.filter import F

from nornir.plugins.tasks import networking
from nornir.plugins.functions.text import print_result

import cnaas_nms.confpush.nornir_helper
from cnaas_nms.cmdb.session import session_scope
from cnaas_nms.cmdb.device import Device

import datetime

def get_inventory():
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    return Inventory.serialize(nr.inventory).dict()

def get_facts(hostname=None, group=None):
    """Get facts about devices using NAPALM getfacts. Defaults to querying all devices in inventory.

    Args:
        hostname (str): Optional hostname of device to query
        group (str): Optional group of devices to query

    Returns:
        Nornir result object
    """
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    if hostname:
        nr_filtered = nr.filter(name=hostname)
    elif group:
        nr_filtered = nr.filter(F(groups__contains=group))
    else:
        nr_filtered = nr

    result = nr_filtered.run(task=networking.napalm_get, getters=["facts"])
    print_result(result)

    return result

def update_inventory(hostname, site='default'):
    """Update CMDB inventory with information gathered from device.

    Args:
        hostname (str): Hostname of device to update

    Returns:
        python dict with any differances of update

    Raises:
        napalm.base.exceptions.ConnectionException: Can't connect to specified device
    """
    # TODO: Handle napalm.base.exceptions.ConnectionException ?
    result = get_facts(hostname=hostname)[hostname][0]

    if result.failed == True:
        raise Exception
    
    facts = result.result['facts']
    with session_scope() as session:
        d = session.query(Device).\
            filter(Device.hostname == hostname).\
            one()
        attr_map = {
            # Map NAPALM getfacts name -> device.Device member name
            'vendor': 'vendor',
            'model': 'model',
            'os_version': 'os_version',
            'serial_number': 'serial',
        }
        diff = {}
        # Update any attributes that has changed, save diff
        for dict_key, obj_mem in attr_map.items():
            obj_data = d.__getattribute__(obj_mem)
            if facts[dict_key] and obj_data != facts[dict_key]:
                diff[obj_mem] = {'old': obj_data,
                                 'new': facts[dict_key]
                                 }
                d.__setattr__(obj_mem, facts[dict_key])
        d.last_seen = datetime.datetime.now()
        session.commit()
        return diff
