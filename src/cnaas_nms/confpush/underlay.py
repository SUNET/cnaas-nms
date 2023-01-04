from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from typing import Optional

from sqlalchemy.orm import load_only

from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.db.reservedip import ReservedIP
from cnaas_nms.db.settings import get_settings


def find_free_infra_ip(session) -> Optional[IPv4Address]:
    """Returns first free IPv4 infra IP."""
    used_ips = []
    device_query = session.query(Device).filter(Device.infra_ip is not None).options(load_only("infra_ip"))
    for device in device_query:
        used_ips.append(device.infra_ip)
    settings, settings_origin = get_settings(device_type=DeviceType.CORE)
    infra_ip_net = IPv4Network(settings["underlay"]["infra_lo_net"])
    for num, net in enumerate(infra_ip_net.subnets(new_prefix=32)):
        ipaddr = IPv4Address(net.network_address)
        if ipaddr in used_ips:
            continue
        else:
            return ipaddr
    return None


def find_free_mgmt_lo_ip(session) -> Optional[IPv4Address]:
    """Returns first free IPv4 infra IP."""
    used_ips = []
    reserved_ips = []
    device_query = session.query(Device).filter(Device.management_ip is not None).options(load_only("management_ip"))
    for device in device_query:
        used_ips.append(device.management_ip)
    reserved_ip_query = session.query(ReservedIP).options(load_only("ip"))
    for reserved_ip in reserved_ip_query:
        reserved_ips.append(reserved_ip.ip)

    settings, settings_origin = get_settings(device_type=DeviceType.CORE)
    mgmt_lo_net = IPv4Network(settings["underlay"]["mgmt_lo_net"])
    for num, net in enumerate(mgmt_lo_net.subnets(new_prefix=32)):
        ipaddr = IPv4Address(net.network_address)
        if ipaddr in used_ips:
            continue
        if ipaddr in reserved_ips:
            continue
        else:
            return ipaddr
    return None


def find_free_infra_linknet(session) -> Optional[IPv4Network]:
    """Returns first free IPv4 infra linknet (/31)."""
    used_linknets = []
    linknet_query = session.query(Linknet).filter(Linknet.device_a_ip is not None)
    ln: Linknet
    for ln in linknet_query:
        used_linknets.append(IPv4Interface(ln.ipv4_network).network)

    settings, settings_origin = get_settings(device_type=DeviceType.CORE)
    infra_ip_net = IPv4Network(settings["underlay"]["infra_link_net"])
    for num, net in enumerate(infra_ip_net.subnets(new_prefix=31)):
        if net in used_linknets:
            continue
        else:
            return net
    return None
