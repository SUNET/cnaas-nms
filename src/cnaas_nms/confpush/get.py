import datetime
import re
import hashlib

from typing import Optional, List, Dict

from nornir.core.filter import F
from nornir.core.task import AggregatedResult
from nornir_napalm.plugins.tasks import napalm_get
from nornir_utils.plugins.functions import print_result

import cnaas_nms.confpush.nornir_helper
from cnaas_nms.db.device import Device, DeviceType, DeviceState
from cnaas_nms.tools.log import get_logger
from cnaas_nms.db.interface import Interface, InterfaceConfigType, InterfaceError


def get_inventory():
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    return nr.dict()['inventory']


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

    result = nr_filtered.run(task=napalm_get, getters=["lldp_neighbors"])
    print_result(result)

    return result


def get_uplinks(session, hostname: str, recheck: bool = False,
                neighbors: Optional[List[Device]] = None,
                linknets = None) -> Dict[str, str]:
    """Returns dict with mapping of interface -> neighbor hostname"""
    logger = get_logger()
    uplinks = {}

    dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
    if not recheck:
        current_uplinks: List[Interface] = session.query(Interface).\
            filter(Interface.device == dev).\
            filter(Interface.configtype == InterfaceConfigType.ACCESS_UPLINK).all()
        uplink_intf: Interface
        for uplink_intf in current_uplinks:
            try:
                uplinks[uplink_intf.name] = uplink_intf.data['neighbor']
            except Exception as e:
                continue
        if 1 <= len(uplinks) <= 2:
            logger.debug("Existing uplinks for device {} found: {}".
                         format(hostname, ', '.join(["{}: {}".format(ifname, hostname)
                                                     for ifname, hostname in uplinks.items()])))
            return uplinks

    neighbor_d: Device
    if not neighbors:
        neighbors = dev.get_neighbors(session)

    for neighbor_d in neighbors:
        if neighbor_d.device_type == DeviceType.DIST:
            for linknet in dev.get_links_to(session, neighbor_d):
                local_if = linknet.get_port(dev.id)
                # Neighbor interface ifclass is already verified in
                # update_linknets -> verify_peer_iftype
                uplinks[local_if] = neighbor_d.hostname
        elif neighbor_d.device_type == DeviceType.ACCESS:
            intfs: List[Interface] = session.query(Interface).filter(Interface.device == neighbor_d).\
                filter(Interface.configtype == InterfaceConfigType.ACCESS_DOWNLINK).all()
            if not intfs:
                continue
            try:
                local_if = dev.get_neighbor_local_ifname(session, neighbor_d)
                remote_if = neighbor_d.get_neighbor_local_ifname(session, dev)
            except ValueError as e:
                logger.debug("Ignoring possible uplinks to neighbor {}: {}".format(
                    neighbor_d.hostname, e))
                continue

            intf: Interface
            for intf in intfs:
                if intf.name == remote_if:
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
            for local_if in dev.get_neighbor_local_ifnames(session, neighbor_d):
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
    nrresult = nr_filtered.run(task=napalm_get, getters=["interfaces"])
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


def verify_peer_iftype(session, local_dev: Device,
                       local_device_settings: dict, local_if: str,
                       remote_dev: Device,
                       remote_device_settings: dict, remote_if: str):
    """Verify that both peers of a linknet are configured with the
    correct interfaces classes.

    Returns:
        bool: True if redundant linknet is required.

    Raises:
        InterfaceError: Incompatible interface found
    """

    # Make sure interface with peers are configured in settings for CORE and DIST devices
    if remote_dev.device_type in [DeviceType.DIST, DeviceType.CORE]:
        match = False
        for intf in remote_device_settings['interfaces']:
            if intf['name'] == remote_if:
                match = True
        if not match:
            raise InterfaceError("Peer device interface is not configured: "
                                 "{} {}".format(remote_dev.hostname,
                                                remote_if))
    if local_dev.device_type in [DeviceType.DIST, DeviceType.CORE]:
        match = False
        for intf in local_device_settings['interfaces']:
            if intf['name'] == local_if:
                match = True
        if not match:
            raise InterfaceError("Local device interface is not configured: "
                                 "{} {}".format(local_dev.hostname,
                                                local_if))

    # Make sure linknets between CORE/DIST devices are configured as fabric
    if local_dev.device_type in [DeviceType.DIST, DeviceType.CORE] and \
            remote_dev.device_type in [DeviceType.DIST, DeviceType.CORE]:
        for intf in local_device_settings['interfaces']:
            if intf['name'] == local_if and intf['ifclass'] != 'fabric':
                raise InterfaceError("Local device interface is not configured as fabric: "
                                     "{} {} ifclass: {}".format(local_dev.hostname,
                                                                intf['name'],
                                                               intf['ifclass']))
        for intf in remote_device_settings['interfaces']:
            if intf['name'] == remote_if and intf['ifclass'] != 'fabric':
                raise InterfaceError("Peer device interface is not configured as fabric: "
                                     "{} {} ifclass: {}".format(remote_dev.hostname,
                                                                intf['name'],
                                                                intf['ifclass']))

    # Make sure that an access switch is connected to an interface
    # configured as "downlink" on the remote end
    if local_dev.device_type == DeviceType.ACCESS and remote_dev.device_type == DeviceType.DIST:
        for intf in remote_device_settings['interfaces']:
            if intf['name'] == remote_if and intf['ifclass'] != 'downlink':
                raise InterfaceError("Peer device interface is not configured as downlink: "
                                     "{} {} ifclass: {}".format(remote_dev.hostname,
                                                                intf['name'],
                                                                intf['ifclass']))
            if intf['name'] == remote_if and intf['ifclass'] == 'downlink' and \
                    not intf['redundant_link']:
                return False

    elif local_dev.device_type == DeviceType.ACCESS and remote_dev.device_type == DeviceType.ACCESS:
        # In case we are doing ZTP init of MLAG pair the peer device should not be of type
        # access yet, so these checks should not fail even though remote interface is not configured
        remote_intf: Optional[Interface] = session.query(Interface).\
            filter((Interface.device == remote_dev) & (Interface.name == remote_if)).\
            one_or_none()
        if not remote_intf:
            raise InterfaceError("Peer device interface not found in database: {} {}".format(
                remote_dev.hostname, remote_if
            ))
        if remote_intf.configtype == InterfaceConfigType.MLAG_PEER:
            pass
        elif remote_intf.configtype != InterfaceConfigType.ACCESS_DOWNLINK:
            raise InterfaceError(
                "Peer device interface not configured as ACCESS_DOWNLINK: {} {}".format(
                    remote_dev.hostname, remote_if
                ))
        if 'redundant_link' in remote_intf.data and not remote_intf.data['redundant_link']:
            return False

    return True
