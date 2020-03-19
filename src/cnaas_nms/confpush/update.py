from typing import Optional, List

from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import Device, DeviceType, DeviceState
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.confpush.get import get_interfaces_names, get_uplinks, \
    filter_interfaces, get_mlag_ifs
from cnaas_nms.tools.log import get_logger


def update_interfacedb_worker(session, dev: Device, replace: bool, delete: bool,
                              mlag_peer_hostname: str) -> List[dict]:
    """Perform actual work of updating database for update_interfacedb"""
    logger = get_logger()
    ret = []

    iflist = get_interfaces_names(dev.hostname)
    uplinks = get_uplinks(session, dev.hostname)
    mlag_ifs = get_mlag_ifs(session, dev.hostname)
    phy_interfaces = filter_interfaces(iflist, platform=dev.platform, include='physical')

    for intf_name in phy_interfaces:
        intf: Interface = session.query(Interface).filter(Interface.device == dev). \
            filter(Interface.name == intf_name).one_or_none()
        if intf:
            new_intf = False
        else:
            new_intf = True
            intf: Interface = Interface()
        if not new_intf and delete:  # 'not new_intf' means interface exists in database
            logger.debug("Deleting interface {} on device {} from interface DB".format(
                intf_name, dev.hostname
            ))
            session.delete(intf)
            continue
        elif not new_intf and not replace:
            continue
        logger.debug("New/updated physical interface found on device {}: {}".format(
            dev.hostname, intf_name
        ))
        if intf_name in uplinks.keys():
            intf.configtype = InterfaceConfigType.ACCESS_UPLINK
            intf.data = {'neighbor': uplinks[intf_name]}
        elif intf_name in mlag_ifs.keys():
            intf.configtype = InterfaceConfigType.MLAG_PEER
            intf.data = {'neighbor': mlag_ifs[intf_name]}
        else:
            intf.configtype = InterfaceConfigType.ACCESS_AUTO
        intf.name = intf_name
        intf.device = dev
        if new_intf:
            session.add(intf)
        ret.append(intf.as_dict())
    return ret


def update_interfacedb(hostname: str, replace: bool = False, delete: bool = False) \
        -> List[dict]:
    """Update interface DB with any new physical interfaces for specified device.
    If replace is set, any existing records in the database will get overwritten.
    If delete is set, all entries in database for this device will be removed.

    Returns:
        List of interfaces that was added to DB
    """
    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not dev:
            raise ValueError(f"Hostname {hostname} not found in database")
        if dev.state != DeviceState.MANAGED:
            raise ValueError(f"Hostname {hostname} is not a managed device")
        if dev.device_type != DeviceType.ACCESS:
            raise ValueError("This function currently only supports access devices")

        result = update_interfacedb_worker(session, dev, replace, delete)

        if result:
            dev.synchronized = False
    return result


def reset_interfacedb(hostname: str):
    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not dev:
            raise ValueError(f"Hostname {hostname} not found in database")

        ret = session.query(Interface).filter(Interface.device == dev).delete()
        return ret


