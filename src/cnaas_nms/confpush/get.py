from nornir import InitNornir

from nornir.core.deserializer.inventory import Inventory
from nornir.core.filter import F

from nornir.plugins.tasks import networking
from nornir.plugins.functions.text import print_result

import cnaas_nms.confpush.nornir_helper
from cnaas_nms.cmdb.session import session_scope
from cnaas_nms.cmdb.device import Device
from cnaas_nms.cmdb.linknet import Linknet

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

def get_neighbors(hostname=None, group=None):
    """Get neighbor information from device

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

    result = nr_filtered.run(task=networking.napalm_get, getters=["lldp_neighbors"])
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

def update_linknets(hostname):
    """Update linknet data for specified device using LLDP neighbor data.
    """
    result = get_neighbors(hostname=hostname)[hostname][0]
    if result.failed == True:
        raise Exception
    neighbors = result.result['lldp_neighbors']

    ret = []

    with session_scope() as session:
        local_device_inst = session.query(Device).filter(Device.hostname == hostname).one()
        print(local_device_inst.id)

        for local_if, data in neighbors.items():
            print(f"Local: {local_if}, remote: {data[0]['hostname']} {data[0]['port']}")
            remote_device_inst = session.query(Device).\
                filter(Device.hostname == data[0]['hostname']).one()
            if not remote_device_inst:
                print(f"Unknown connected device: {data[0]['hostname']}")
                continue
            print(f"Remote device found, device id: {remote_device_inst.id}")

            # Check if linknet object already exists in database
            local_devid = local_device_inst.id
            check_linknet = session.query(Linknet).\
                filter(
                    ((Linknet.device_a_id == local_devid) & (Linknet.device_a_port == local_if))
                    |
                    ((Linknet.device_b_id == local_devid) & (Linknet.device_b_port == local_if))
                ).one_or_none()
            if check_linknet:
                print(f"Found entry: {check_linknet.id}")
                #TODO: check info and update if necessary
            else:
                new_link = Linknet()
                new_link.device_a = local_device_inst
                new_link.device_a_port = local_if
                new_link.device_b = remote_device_inst
                new_link.device_b_port = data[0]['port']
                session.add(new_link)
                ret.append(new_link.as_dict())
