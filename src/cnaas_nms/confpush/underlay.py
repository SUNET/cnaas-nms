from typing import Optional

from ipaddress import IPv4Network, IPv4Address, IPv4Interface
from sqlalchemy.orm import load_only

from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.db.settings import get_settings


def find_free_infra_ip(session) -> Optional[IPv4Address]:
    """Returns first free IPv4 infra IP."""
    used_ips = []
    device_query = session.query(Device). \
        filter(Device.infra_ip != None).options(load_only("infra_ip"))
    for device in device_query:
        used_ips.append(device.infra_ip)

    settings, settings_origin = get_settings(device_type=DeviceType.CORE)
    infra_ip_net = IPv4Network(settings['underlay']['infra_lo_net'])
    for num, net in enumerate(infra_ip_net.subnets(new_prefix=32)):
        ipaddr = IPv4Address(net.network_address)
        if ipaddr in used_ips:
            continue
        else:
            return ipaddr
    return None


def find_free_infra_linknet(session) -> Optional[IPv4Network]:
    """Returns first free IPv4 infra linknet (/31)."""
    used_linknets = []
    linknet_query = session.query(Linknet). \
        filter(Linknet.device_a_ip != None)
    ln: Linknet
    for ln in linknet_query:
        used_linknets.append(IPv4Interface(ln.device_a_ip).network)

    settings, settings_origin = get_settings(device_type=DeviceType.CORE)
    infra_ip_net = IPv4Network(settings['underlay']['infra_link_net'])
    for num, net in enumerate(infra_ip_net.subnets(new_prefix=31)):
        if net in used_linknets:
            continue
        else:
            return net
    return None
