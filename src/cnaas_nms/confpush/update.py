from typing import Optional, List

from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import Device, DeviceType, DeviceState
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.confpush.get import get_interfaces_names, get_uplinks, \
    filter_interfaces, get_interfacedb_ifs, get_optics
from cnaas_nms.tools.log import get_logger

logger = get_logger()


def update_interfacedb(hostname: str, replace: bool = False, delete: bool = False) \
        -> Optional[List[dict]]:
    """Update interface DB with any new physical interfaces for specified device.
    If replace is set, any existing records in the database will get overwritten.
    If delete is set, all entries in database for this device will be removed.

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
        optics = get_optics(hostname).result['optics']
#        existing_ifs = get_interfacedb_ifs(session, hostname)

        updated = False
        for intf_name in phy_interfaces:
            intf: Interface = session.query(Interface).filter(Interface.device == dev).\
                filter(Interface.name == intf_name).one_or_none()
            if intf:
                new_intf = False
            else:
                new_intf = True
                intf: Interface = Interface()
            if not new_intf and delete:
                logger.debug("Deleting interface {} on device {} from interface DB".format(
                    intf_name, dev.hostname
                ))
                session.delete(intf)
                continue
            elif not new_intf and not replace:
                continue
            updated = True
            logger.debug("New/updated physical interface found on device {}: {}".format(
                dev.hostname, intf_name
            ))
            if intf_name in uplinks_ifnames:
                if_optics = optics[intf_name]['physical_channels']['channel'][0]['state']
                tx_power = optics['input_power']['instant']
                rx_power = optics['output_power']['instant']
                intf.configtype = InterfaceConfigType.ACCESS_UPLINK
                intf.data = {'neighbor': neighbor_hostnames[uplinks_ifnames.index(intf_name)],
                             'tx_power': tx_power,
                             'rx_power': rx_power}
            else:
                intf.configtype = InterfaceConfigType.ACCESS_AUTO
            intf.name = intf_name
            intf.device = dev
            if new_intf:
                session.add(intf)
            ret.append(intf.as_dict())
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


