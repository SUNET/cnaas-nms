import datetime
import re
import hashlib

from typing import Optional, Tuple, List, Dict

from nornir.core.filter import F
from nornir.core.task import AggregatedResult
from nornir_napalm.plugins.tasks import napalm_get
from nornir_utils.plugins.functions import print_result

import cnaas_nms.confpush.nornir_helper
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import Device, DeviceType, DeviceState
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.tools.log import get_logger
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.confpush.underlay import find_free_infra_linknet
from cnaas_nms.db.settings import get_settings


def get_inventory():
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    return nr.dict()


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

    result = nr_filtered.run(task=napalm_get, getters=["facts"])
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
        if len(uplinks) == 2:
            logger.debug("Existing uplinks for device {} found: {}".
                         format(hostname, ', '.join(["{}: {}".format(ifname, hostname)
                                                     for ifname, hostname in uplinks.items()])))
            return uplinks

    neighbor_d: Device
    if not neighbors:
        neighbors = dev.get_neighbors(session)

    for neighbor_d in neighbors:
        if neighbor_d.device_type == DeviceType.DIST:
            local_if = dev.get_neighbor_local_ifname(session, neighbor_d)
            # Neighbor interface ifclass is already verified in
            # update_linknets -> verify_peer_iftype
            if local_if:
                uplinks[local_if] = neighbor_d.hostname
        elif neighbor_d.device_type == DeviceType.ACCESS:
            intfs: Interface = session.query(Interface).filter(Interface.device == neighbor_d).\
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


def verify_peer_iftype(local_hostname: str, local_devtype: DeviceType,
                       local_device_settings: dict, local_if: str,
                       remote_hostname: str, remote_devtype: DeviceType,
                       remote_device_settings: dict, remote_if: str):
    # Make sure interface with peers are configured in settings for CORE and DIST devices
    if remote_devtype in [DeviceType.DIST, DeviceType.CORE]:
        match = False
        for intf in remote_device_settings['interfaces']:
            if intf['name'] == remote_if:
                match = True
        if not match:
            raise ValueError("Peer device interface is not configured: "
                             "{} {}".format(remote_hostname,
                                            remote_if))
    if local_devtype in [DeviceType.DIST, DeviceType.CORE]:
        match = False
        for intf in local_device_settings['interfaces']:
            if intf['name'] == local_if:
                match = True
        if not match:
            raise ValueError("Local device interface is not configured: "
                             "{} {}".format(local_hostname,
                                            local_if))

    # Make sure linknets between CORE/DIST devices are configured as fabric
    if local_devtype in [DeviceType.DIST, DeviceType.CORE] and \
            remote_devtype in [DeviceType.DIST, DeviceType.CORE]:
        for intf in local_device_settings['interfaces']:
            if intf['name'] == local_if and intf['ifclass'] != 'fabric':
                raise ValueError("Local device interface is not configured as fabric: "
                                 "{} {} ifclass: {}".format(local_hostname,
                                                            intf['name'],
                                                            intf['ifclass']))
        for intf in remote_device_settings['interfaces']:
            if intf['name'] == remote_if and intf['ifclass'] != 'fabric':
                raise ValueError("Peer device interface is not configured as fabric: "
                                 "{} {} ifclass: {}".format(remote_hostname,
                                                            intf['name'],
                                                            intf['ifclass']))

    # Make sure that an access switch is connected to an interface
    # configured as "downlink" on the remote end
    if local_devtype == DeviceType.ACCESS and remote_devtype == DeviceType.DIST:
        for intf in remote_device_settings['interfaces']:
            if intf['name'] == remote_if and intf['ifclass'] != 'downlink':
                raise ValueError("Peer device interface is not configured as downlink: "
                                 "{} {} ifclass: {}".format(remote_hostname,
                                                            intf['name'],
                                                            intf['ifclass']))


def update_linknets(session, hostname: str, devtype: DeviceType,
                    ztp_hostname: Optional[str] = None, dry_run: bool = False):
    """Update linknet data for specified device using LLDP neighbor data.
    """
    logger = get_logger()
    result = get_neighbors(hostname=hostname)[hostname][0]
    if result.failed:
        raise Exception("Could not get LLDP neighbors for {}".format(hostname))
    neighbors = result.result['lldp_neighbors']
    if ztp_hostname:
        settings_hostname = ztp_hostname
    else:
        settings_hostname = hostname

    ret = []

    local_device_inst: Device = session.query(Device).filter(Device.hostname == hostname).one()
    logger.debug("Updating linknets for device {} of type {}...".format(
        local_device_inst.id, devtype.name))

    for local_if, data in neighbors.items():
        logger.debug(f"Local: {local_if}, remote: {data[0]['hostname']} {data[0]['port']}")
        remote_device_inst: Device = session.query(Device).\
            filter(Device.hostname == data[0]['hostname']).one_or_none()
        if not remote_device_inst:
            logger.debug(f"Unknown neighbor device, ignoring: {data[0]['hostname']}")
            continue
        if remote_device_inst.state in [DeviceState.DISCOVERED, DeviceState.INIT]:
            # In case of MLAG init the peer does not have the correct devtype set yet,
            # use same devtype as local device instead
            remote_devtype = devtype
        elif remote_device_inst.state not in [DeviceState.MANAGED, DeviceState.UNMANAGED]:
            logger.debug("Neighbor device has invalid state, ignoring: {}".format(
                data[0]['hostname']))
            continue
        else:
            remote_devtype = remote_device_inst.device_type

        logger.debug(f"Remote device found, device id: {remote_device_inst.id}")

        local_device_settings, _ = get_settings(settings_hostname,
                                                devtype,
                                                local_device_inst.model
                                                )
        remote_device_settings, _ = get_settings(remote_device_inst.hostname,
                                                 remote_devtype,
                                                 remote_device_inst.model
                                                 )

        verify_peer_iftype(hostname, devtype,
                           local_device_settings, local_if,
                           remote_device_inst.hostname, remote_device_inst.device_type,
                           remote_device_settings, data[0]['port'])

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
            logger.debug(f"Found existing linknet id: {check_linknet.id}")
            if (
                    (
                        check_linknet.device_a_id == local_devid
                        and check_linknet.device_a_port == local_if
                        and check_linknet.device_b_id == remote_device_inst.id
                        and check_linknet.device_b_port == data[0]['port']
                    )
                    or
                    (
                        check_linknet.device_a_id == local_devid
                        and check_linknet.device_a_port == local_if
                        and check_linknet.device_b_id == remote_device_inst.id
                        and check_linknet.device_b_port == data[0]['port']
                    )
            ):
                # All info is the same, no update required
                continue
            else:
                # TODO: update instead of delete+new insert?
                if not dry_run:
                    session.delete(check_linknet)
                    session.commit()

        if devtype in [DeviceType.CORE, DeviceType.DIST] and \
                remote_device_inst.device_type in [DeviceType.CORE, DeviceType.DIST]:
            ipv4_network = find_free_infra_linknet(session)
        else:
            ipv4_network = None
        new_link = Linknet.create_linknet(
            session,
            hostname_a=local_device_inst.hostname,
            interface_a=local_if,
            hostname_b=remote_device_inst.hostname,
            interface_b=data[0]['port'],
            ipv4_network=ipv4_network,
            strict_check=not dry_run  # Don't do strict check if this is a dry_run
        )
        if not dry_run:
            local_device_inst.synchronized = False
            remote_device_inst.synchronized = False
            session.add(new_link)
            session.commit()
        else:
            # Make sure linknet object is not added to session because of foreign key load
            session.expunge(new_link)
        # Make return data pretty
        ret_dict = {
            'device_a_hostname': local_device_inst.hostname,
            'device_b_hostname': remote_device_inst.hostname,
            **new_link.as_dict()
        }
        del ret_dict['id']
        del ret_dict['device_a_id']
        del ret_dict['device_b_id']
        ret.append({k: ret_dict[k] for k in sorted(ret_dict)})
    return ret
