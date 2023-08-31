import hashlib
import re
from typing import Dict, List, Optional

from netutils.config import compliance
from netutils.lib_mapper import NAPALM_LIB_MAPPER
from nornir.core.filter import F
from nornir.core.task import AggregatedResult
from nornir_napalm.plugins.tasks import napalm_get
from nornir_utils.plugins.functions import print_result

import cnaas_nms.devicehandler.nornir_helper
from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.device_vars import expand_interface_settings
from cnaas_nms.db.interface import Interface, InterfaceConfigType, InterfaceError
from cnaas_nms.db.session import sqla_session
from cnaas_nms.tools.log import get_logger


def get_inventory():
    nr = cnaas_nms.devicehandler.nornir_helper.cnaas_init()
    return nr.dict()["inventory"]


def get_running_config(hostname: str) -> Optional[str]:
    nr = cnaas_nms.devicehandler.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname).filter(managed=True)
    nr_result = nr_filtered.run(task=napalm_get, getters=["config"])
    if nr_result[hostname].failed:
        raise nr_result[hostname][0].exception
    else:
        return nr_result[hostname].result["config"]["running"]


def get_running_config_interface(session: sqla_session, hostname: str, interface: str) -> str:
    running_config = get_running_config(hostname)
    dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
    os_parser = compliance.parser_map[NAPALM_LIB_MAPPER.get(dev.platform)]
    config_parsed = os_parser(running_config)
    ret = []
    for line in config_parsed.config_lines:
        if f"interface {interface}" in line.parents:
            ret.append(line.config_line.strip())
    return "\n".join(ret)


def calc_config_hash(hostname, config):
    try:
        hash_object = hashlib.sha256(config.encode())
    except Exception:
        raise Exception(f"Failed to get running configuration from {hostname}")
    return hash_object.hexdigest()


def get_neighbors(hostname: Optional[str] = None, group: Optional[str] = None) -> AggregatedResult:
    """Get neighbor information from device

    Args:
        hostname: Optional hostname of device to query
        group: Optional group of devices to query

    Returns:
        Nornir result object
    """
    nr = cnaas_nms.devicehandler.nornir_helper.cnaas_init()
    if hostname:
        nr_filtered = nr.filter(name=hostname)
    elif group:
        nr_filtered = nr.filter(F(groups__contains=group))
    else:
        nr_filtered = nr

    result = nr_filtered.run(task=napalm_get, getters=["lldp_neighbors"])
    print_result(result)

    return result


def get_uplinks(
    session,
    hostname: str,
    recheck: bool = False,
    neighbors: Optional[List[Device]] = None,
    linknets: Optional[List[dict]] = None,
) -> Dict[str, str]:
    """Returns dict with mapping of interface -> neighbor hostname"""
    logger = get_logger()
    uplinks = {}

    dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
    if not recheck:
        current_uplinks: List[Interface] = (
            session.query(Interface)
            .filter(Interface.device == dev)
            .filter(Interface.configtype == InterfaceConfigType.ACCESS_UPLINK)
            .all()
        )
        uplink_intf: Interface
        for uplink_intf in current_uplinks:
            try:
                uplinks[uplink_intf.name] = uplink_intf.data["neighbor"]
            except Exception:  # noqa: S110
                continue
        if 1 <= len(uplinks) <= 2:
            logger.debug(
                "Existing uplinks for device {} found: {}".format(
                    hostname, ", ".join(["{}: {}".format(ifname, hostname) for ifname, hostname in uplinks.items()])
                )
            )
            return uplinks

    neighbor_d: Device
    if not neighbors:
        neighbors = dev.get_neighbors(session, linknets)

    for neighbor_d in neighbors:
        if neighbor_d.device_type == DeviceType.DIST:
            local_ifs = dev.get_neighbor_ifnames(session, neighbor_d, linknets)
            # Neighbor interface ifclass is already verified in
            # update_linknets -> verify_peer_iftype
            for local_if in local_ifs:
                uplinks[local_if[0]] = neighbor_d.hostname
        elif neighbor_d.device_type == DeviceType.ACCESS:
            dl_intfs: List[Interface] = (
                session.query(Interface)
                .filter(Interface.device == neighbor_d)
                .filter(Interface.configtype == InterfaceConfigType.ACCESS_DOWNLINK)
                .all()
            )
            local_ifs = dev.get_neighbor_ifnames(session, neighbor_d, linknets)

            dl_intf_names = []
            intf: Interface
            for dl_intf in dl_intfs:
                dl_intf_names.append(dl_intf.name)

            for local_if in local_ifs:
                if local_if[1] not in dl_intf_names:
                    logger.warning(
                        "Interface {} from {} to {} not configured as DOWNLINK".format(
                            local_if[1], neighbor_d.hostname, dev.hostname
                        )
                    )
                uplinks[local_if[0]] = neighbor_d.hostname

    logger.debug(
        "Uplinks for device {} detected: {}".format(
            hostname, ", ".join(["{}: {}".format(ifname, hostname) for ifname, hostname in uplinks.items()])
        )
    )

    return uplinks


def get_local_ifnames(local_devid: int, peer_devid: int, linknets: List[dict]) -> List[str]:
    ifnames = []
    if not linknets:
        return ifnames
    for linknet in linknets:
        if linknet["device_a_id"] == local_devid and linknet["device_b_id"] == peer_devid:
            ifnames.append(linknet["device_a_port"])
        elif linknet["device_b_id"] == local_devid and linknet["device_a_id"] == peer_devid:
            ifnames.append(linknet["device_b_port"])
    return ifnames


def get_mlag_ifs(
    session, dev: Device, mlag_peer_hostname: str, linknets: Optional[List[dict]] = None
) -> Dict[str, int]:
    """Returns dict with mapping of interface -> neighbor id
    Return id instead of hostname since mlag peer will change hostname during init"""
    logger = get_logger()
    mlag_ifs = {}

    dev = session.query(Device).filter(Device.hostname == dev.hostname).one()
    for neighbor_d in dev.get_neighbors(session, linknets=linknets):
        if neighbor_d.hostname == mlag_peer_hostname:
            for local_if in get_local_ifnames(dev.id, neighbor_d.id, linknets):
                mlag_ifs[local_if] = neighbor_d.id
    logger.debug(
        "MLAG peer interfaces for device {} detected: {}".format(
            dev.hostname, ", ".join(["{}: {}".format(ifname, hostname) for ifname, hostname in mlag_ifs.items()])
        )
    )
    return mlag_ifs


def get_interfaces(hostname: str) -> AggregatedResult:
    """Get a NAPALM/Nornir aggregated result of the current interfaces
    on the specified device.
    """
    nr = cnaas_nms.devicehandler.nornir_helper.cnaas_init()
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
        raise Exception("Could not get facts from device {}: {}".format(hostname, getfacts_task.result))
    else:
        return list(getfacts_task.result["interfaces"].keys())


def filter_interfaces(iflist, platform=None, include=None):
    # TODO: include pattern matching from external configurable file
    ret = []
    junos_phy_r = r"^[gx]e-([0-9]+\/)+[0-9]+$"
    for intf in iflist:
        if include == "physical":
            if platform == "junos":
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


def verify_peer_iftype(
    session,
    local_dev: Device,
    local_device_settings: dict,
    local_if: str,
    remote_dev: Device,
    remote_device_settings: dict,
    remote_if: str,
):
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
        for intf in expand_interface_settings(remote_device_settings["interfaces"]):
            if intf["name"] == remote_if:
                match = True
        if not match:
            raise InterfaceError(
                "Peer device interface is not configured: " "{} {}".format(remote_dev.hostname, remote_if)
            )
    if local_dev.device_type in [DeviceType.DIST, DeviceType.CORE]:
        match = False
        for intf in expand_interface_settings(local_device_settings["interfaces"]):
            if intf["name"] == local_if:
                match = True
        if not match:
            raise InterfaceError(
                "Local device interface is not configured: " "{} {}".format(local_dev.hostname, local_if)
            )

    # Make sure linknets between CORE/DIST devices are configured as fabric
    if local_dev.device_type in [DeviceType.DIST, DeviceType.CORE] and remote_dev.device_type in [
        DeviceType.DIST,
        DeviceType.CORE,
    ]:
        for intf in expand_interface_settings(local_device_settings["interfaces"]):
            if intf["name"] == local_if and intf["ifclass"] != "fabric":
                raise InterfaceError(
                    "Local device interface is not configured as fabric: "
                    "{} {} ifclass: {}".format(local_dev.hostname, intf["name"], intf["ifclass"])
                )
        for intf in expand_interface_settings(remote_device_settings["interfaces"]):
            if intf["name"] == remote_if and intf["ifclass"] != "fabric":
                raise InterfaceError(
                    "Peer device interface is not configured as fabric: "
                    "{} {} ifclass: {}".format(remote_dev.hostname, intf["name"], intf["ifclass"])
                )

    # Make sure that an access switch is connected to an interface
    # configured as "downlink" on the remote end
    if local_dev.device_type == DeviceType.ACCESS and remote_dev.device_type == DeviceType.DIST:
        for intf in expand_interface_settings(remote_device_settings["interfaces"]):
            if intf["name"] == remote_if and intf["ifclass"] != "downlink":
                raise InterfaceError(
                    "Peer device interface is not configured as downlink: "
                    "{} {} ifclass: {}".format(remote_dev.hostname, intf["name"], intf["ifclass"])
                )
            if intf["name"] == remote_if and intf["ifclass"] == "downlink" and not intf["redundant_link"]:
                return False

    elif local_dev.device_type == DeviceType.ACCESS and remote_dev.device_type == DeviceType.ACCESS:
        # In case we are doing ZTP init of MLAG pair the peer device should not be of type
        # access yet, so these checks should not fail even though remote interface is not configured
        remote_intf: Optional[Interface] = (
            session.query(Interface)
            .filter((Interface.device == remote_dev) & (Interface.name == remote_if))
            .one_or_none()
        )
        if not remote_intf:
            raise InterfaceError(
                "Peer device interface not found in database: {} {}".format(remote_dev.hostname, remote_if)
            )
        if remote_intf.configtype == InterfaceConfigType.MLAG_PEER:
            pass
        elif remote_intf.configtype != InterfaceConfigType.ACCESS_DOWNLINK:
            raise InterfaceError(
                "Peer device interface not configured as ACCESS_DOWNLINK: {} {}".format(remote_dev.hostname, remote_if)
            )
        if remote_intf.data and "redundant_link" in remote_intf.data and not remote_intf.data["redundant_link"]:
            return False

    return True
