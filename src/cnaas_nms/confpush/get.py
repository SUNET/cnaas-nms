import datetime
import re
import hashlib

from typing import Optional, Tuple, List, Dict

from nornir.core.deserializer.inventory import Inventory
from nornir.core.filter import F
from nornir.plugins.tasks import networking
from nornir.plugins.functions.text import print_result
from nornir.core.task import AggregatedResult
from nornir.plugins.tasks.networking import napalm_get

import cnaas_nms.confpush.nornir_helper
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.tools.log import get_logger
from cnaas_nms.db.interface import Interface


def get_inventory():
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    return Inventory.serialize(nr.inventory).dict()


def get_running_config(hostname):
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    if hostname:
        nr_filtered = nr.filter(name=hostname).filter(managed=True)
    else:
        nr_filtered = nr.filter(managed=True)
    nr_result = nr_filtered.run(task=napalm_get, getters=["config"])
    return nr_result[hostname].result


def calc_config_hash(hostname, config):
    try:
        hash_object = hashlib.sha256(config.encode())
    except Exception:
        raise Exception(f'Failed to get running configuration from {hostname}')
    return hash_object.hexdigest()


def get_facts(hostname: Optional[str] = None, group: Optional[str] = None)\
        -> AggregatedResult:
    """Get facts about devices using NAPALM getfacts. Defaults to querying all
    devices in the inventory.

    Args:
        hostname: Optional hostname of device to query
        group: Optional group of devices to query

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


def get_neighbors(hostname: Optional[str] = None, group: Optional[str] = None)\
        -> AggregatedResult:
    """Get neighbor information from device

    Args:
        hostname: Optional hostname of device to query
        group: Optional group of devices to query

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


def get_uplinks(session, hostname: str) -> Dict[str, str]:
    """Returns dict with mapping of interface -> neighbor hostname"""
    logger = get_logger()
    # TODO: check if uplinks are already saved in database?
    uplinks = {}

    dev = session.query(Device).filter(Device.hostname == hostname).one()
    for neighbor_d in dev.get_neighbors(session):
        if neighbor_d.device_type == DeviceType.DIST:
            local_if = dev.get_neighbor_local_ifname(session, neighbor_d)
            if local_if:
                uplinks[local_if] = neighbor_d.hostname
    logger.debug("Uplinks for device {} detected: {}".
                 format(hostname, ', '.join(["{}: {}".format(ifname, hostname)
                                             for ifname, hostname in uplinks.items()])))

    return uplinks


def get_mlag_ifs(session, hostname, mlag_peer_hostname) -> Dict[str, int]:
    """Returns dict with mapping of interface -> neighbor id
    Return id instead of hostname since mlag peer will change hostname during init"""
    logger = get_logger()
    mlag_ifs = {}

    dev = session.query(Device).filter(Device.hostname == hostname).one()
    for neighbor_d in dev.get_neighbors(session):
        if neighbor_d.hostname == mlag_peer_hostname:
            local_if = dev.get_neighbor_local_ifname(session, neighbor_d)
            if local_if:
                mlag_ifs[local_if] = neighbor_d.id
    logger.debug("MLAG peer interfaces for device {} detected: {}".
                 format(hostname, ', '.join(["{}: {}".format(ifname, hostname)
                                             for ifname, hostname in mlag_ifs.items()])))
    return mlag_ifs


def get_interfaces(hostname: str) -> AggregatedResult:
    """Get a NAPALM/Nornir aggregated result of the current interfaces
    on the specified device.
    """
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname)
    if len(nr_filtered.inventory) != 1:
        raise ValueError(f"Hostname {hostname} not found in inventory")
    nrresult = nr_filtered.run(task=networking.napalm_get, getters=["interfaces"])
    return nrresult


def get_interfaces_names(hostname: str) -> List[str]:
    """Get a list of interface names for active interfaces on
    the specified device.
    """
    nrresult = get_interfaces(hostname)
    getfacts_task = nrresult[hostname][0]
    if getfacts_task.failed:
        raise Exception("Could not get facts from device {}: {}".format(
            hostname, getfacts_task.result
        ))
    else:
        return list(getfacts_task.result['interfaces'].keys())


def filter_interfaces(iflist, platform=None, include=None):
    # TODO: include pattern matching from external configurable file
    ret = []
    junos_phy_r = r'^[gx]e-([0-9]+\/)+[0-9]+$'
    for intf in iflist:
        if include == 'physical':
            if platform == 'junos':
                if re.match(junos_phy_r, intf):
                    ret.append(intf)
            else:
                if intf.startswith("Ethernet"):
                    ret.append(intf)
    return ret


def get_interfacedb_ifs(session, hostname: str) -> List[str]:
    ret = []
    dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
    if not dev:
        raise ValueError(f"Hostname {hostname} not found in database")
    ifs: List[Interface] = session.query(Interface).filter(Interface.device == dev).all()
    for intf in ifs:
        ret.append(intf.name)
    return ret


def update_inventory(hostname: str, site='default') -> dict:
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
    if result.failed:
        raise Exception
    facts = result.result['facts']
    with sqla_session() as session:
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


def update_linknets(session, hostname):
    """Update linknet data for specified device using LLDP neighbor data.
    """
    logger = get_logger()
    result = get_neighbors(hostname=hostname)[hostname][0]
    if result.failed:
        raise Exception
    neighbors = result.result['lldp_neighbors']

    ret = []

    local_device_inst = session.query(Device).filter(Device.hostname == hostname).one()
    logger.debug("Updating linknets for device {} ...".format(local_device_inst.id))

    for local_if, data in neighbors.items():
        logger.debug(f"Local: {local_if}, remote: {data[0]['hostname']} {data[0]['port']}")
        remote_device_inst = session.query(Device).\
            filter(Device.hostname == data[0]['hostname']).one_or_none()
        if not remote_device_inst:
            logger.info(f"Unknown connected device: {data[0]['hostname']}")
            continue
        logger.debug(f"Remote device found, device id: {remote_device_inst.id}")

        # Check if linknet object already exists in database
        local_devid = local_device_inst.id
        check_linknet = session.query(Linknet).\
            filter(
                ((Linknet.device_a_id == local_devid) & (Linknet.device_a_port == local_if))
                |
                ((Linknet.device_b_id == local_devid) & (Linknet.device_b_port == local_if))
                |
                ((Linknet.device_a_id == remote_device_inst.id) &
                 (Linknet.device_a_port == data[0]['port']))
                |
                ((Linknet.device_b_id == remote_device_inst.id) &
                 (Linknet.device_b_port == data[0]['port']))
            ).one_or_none()
        if check_linknet:
            logger.debug(f"Found entry: {check_linknet.id}")
            if (
                    (       check_linknet.device_a_id == local_devid
                        and check_linknet.device_a_port == local_if
                        and check_linknet.device_b_id == remote_device_inst.id
                        and check_linknet.device_b_port == data[0]['port']
                    )
                    or
                    (       check_linknet.device_a_id == local_devid
                        and check_linknet.device_a_port == local_if
                        and check_linknet.device_b_id == remote_device_inst.id
                        and check_linknet.device_b_port == data[0]['port']
                    )
            ):
                # All info is the same, no update required
                continue
            else:
                # TODO: update instead of delete+new insert?
                session.delete(check_linknet)
                session.commit()

        new_link = Linknet()
        new_link.device_a = local_device_inst
        new_link.device_a_port = local_if
        new_link.device_b = remote_device_inst
        new_link.device_b_port = data[0]['port']
        session.add(new_link)
        ret.append(new_link.as_dict())
    session.commit()
    return ret
