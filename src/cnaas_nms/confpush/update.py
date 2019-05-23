from typing import Optional, List

from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import Device, DeviceType, DeviceState
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.confpush.get import get_interfaces_names, get_uplinks, \
    filter_interfaces, get_interfacedb_ifs
from cnaas_nms.tools.log import get_logger

logger = get_logger()


def update_interfacedb(hostname: str) -> Optional[List[dict]]:
    """Update interface DB with any new physical interfaces for specified device.

    Returns:
        List of interfaces that was added to DB
    """
    ret = []
    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not dev:
            raise ValueError(f"Hostname {hostname} not found in database")
        if dev.state != DeviceState.MANAGED:
            raise ValueError(f"Hostname {hostname} is not a managed device")
        if dev.device_type != DeviceType.ACCESS:
            raise ValueError("This function currently only supports access devices")
        # TODO: add support for dist/core devices?

        iflist = get_interfaces_names(hostname)
        uplinks, neighbor_hostnames = get_uplinks(session, hostname)
        uplinks_ifnames = [x['ifname'] for x in uplinks]
        phy_interfaces = filter_interfaces(iflist, platform=dev.platform, include='physical')
        existing_ifs = get_interfacedb_ifs(session, hostname)

        updated = False
        for intf in phy_interfaces:
            if intf in existing_ifs:
                continue
            updated = True
            logger.debug("New physical interface found on device {}: {}".format(
                dev.hostname, intf
            ))
            new_intf: Interface = Interface()
            if intf in uplinks_ifnames:
                new_intf.configtype = InterfaceConfigType.ACCESS_UPLINK
            else:
                new_intf.configtype = InterfaceConfigType.ACCESS_AUTO
            new_intf.name = intf
            new_intf.device = dev
            session.add(new_intf)
            ret.append(new_intf.as_dict())
        if updated:
            dev.synchronized = False
    return ret


def reset_interfacedb(hostname: str):
    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not dev:
            raise ValueError(f"Hostname {hostname} not found in database")

        ret = session.query(Interface).filter(Interface.device == dev).delete()
        return ret
