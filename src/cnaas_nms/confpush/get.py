import datetime
from typing import Optional, Tuple, List

from nornir.core.deserializer.inventory import Inventory
from nornir.core.filter import F
from nornir.plugins.tasks import networking
from nornir.plugins.functions.text import print_result
from nornir.core.task import AggregatedResult

import cnaas_nms.confpush.nornir_helper
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.tools.log import get_logger
from cnaas_nms.db.interface import Interface

logger = get_logger()


def get_inventory():
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    return Inventory.serialize(nr.inventory).dict()


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


def get_uplinks(session, hostname: str) -> Tuple[List, List]:
    # TODO: check if uplinks are already saved in database?
    uplinks = []
    neighbor_hostnames = []

    dev = session.query(Device).filter(Device.hostname == hostname).one()
    for neighbor_d in dev.get_neighbors(session):
        if neighbor_d.device_type == DeviceType.DIST:
            local_if = dev.get_link_to_local_ifname(session, neighbor_d)
            if local_if:
                uplinks.append({'ifname': local_if})
                neighbor_hostnames.append(neighbor_d.hostname)
    logger.debug("Uplinks for device {} detected: {} neighbor_hostnames: {}". \
                 format(hostname, uplinks, neighbor_hostnames))

    return (uplinks, neighbor_hostnames)


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
    return list(nrresult[hostname][0].result['interfaces'].keys())


def filter_interfaces(iflist, model=None, include=None):
    # TODO: do mapping based on switch model
    ret = []
    for intf in iflist:
        if include == 'physical':
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


def update_linknets(hostname):
    """Update linknet data for specified device using LLDP neighbor data.
    """
    result = get_neighbors(hostname=hostname)[hostname][0]
    if result.failed:
        raise Exception
    neighbors = result.result['lldp_neighbors']

    ret = []

    with sqla_session() as session:
        local_device_inst = session.query(Device).filter(Device.hostname == hostname).one()
        logger.debug("Updating linknets for device {} ...".format(local_device_inst.id))

        for local_if, data in neighbors.items():
            logger.debug(f"Local: {local_if}, remote: {data[0]['hostname']} {data[0]['port']}")
            remote_device_inst = session.query(Device).\
                filter(Device.hostname == data[0]['hostname']).one()
            if not remote_device_inst:
                logger.debug(f"Unknown connected device: {data[0]['hostname']}")
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
