import datetime
from typing import List, Optional
from ipaddress import IPv4Interface, IPv4Address

import netaddr
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.mgmtdomain import Mgmtdomain


def canonical_mac(mac):
    """Return a standardized format of MAC-addresses for CNaaS to
    store in databases etc."""
    na_mac = netaddr.EUI(mac)
    na_mac.dialect = netaddr.mac_bare
    return str(na_mac)


def find_mgmtdomain(session, hostnames: List[str]) -> Optional[Mgmtdomain]:
    """Find the corresponding management domain for a pair of
    distribution switches.

    Args:
        hostnames: A list of two hostnames for the distribution switches

    Raises:
        ValueError: On invalid hostnames etc
    """
    if not isinstance(hostnames, list) or not len(hostnames) == 2:
        raise ValueError(
            "Two uplink devices are required to find a compatible mgmtdomain, got: {}".format(
                hostnames
            ))
    for hostname in hostnames:
        if not Device.valid_hostname(hostname):
            raise ValueError(f"Argument {hostname} is not a valid hostname")
    try:
        device0: Device = session.query(Device).filter(Device.hostname == hostnames[0]).one()
    except NoResultFound:
        raise ValueError(f"hostname {hostnames[0]} not found in device database")
    try:
        device1: Device = session.query(Device).filter(Device.hostname == hostnames[1]).one()
    except NoResultFound:
        raise ValueError(f"hostname {hostnames[1]} not found in device database")

    if device0.device_type == DeviceType.DIST or device1.device_type == DeviceType.DIST:
        if device0.device_type != DeviceType.DIST or device1.device_type != DeviceType.DIST:
            raise ValueError("Both uplink devices must be of same device type: {}, {}".format(
                device0.hostname, device1.hostname
            ))
        try:
            mgmtdomain: Mgmtdomain = session.query(Mgmtdomain).\
                filter(
                    ((Mgmtdomain.device_a == device0) & (Mgmtdomain.device_b == device1))
                    |
                    ((Mgmtdomain.device_a == device1) & (Mgmtdomain.device_b == device0))
                ).one_or_none()
            # If no mgmtdomain has been found, check if there is exactly one mgmtdomain
            # defined that has two core devices as members and use that instead
            if not mgmtdomain:
                mgmtdomain: Mgmtdomain = session.query(Mgmtdomain).filter(
                    (Mgmtdomain.device_a.has(Device.device_type == DeviceType.CORE))
                    |
                    (Mgmtdomain.device_b.has(Device.device_type == DeviceType.CORE))
                ).one_or_none()
        except MultipleResultsFound:
            raise Exception(
                "Found multiple possible mgmtdomains, please remove any redundant mgmtdomains")
    elif device0.device_type == DeviceType.ACCESS or device1.device_type == DeviceType.ACCESS:
        if device0.device_type != DeviceType.ACCESS or device1.device_type != DeviceType.ACCESS:
            raise ValueError("Both uplink devices must be of same device type: {}, {}".format(
                device0.hostname, device1.hostname
            ))
        mgmtdomain: Mgmtdomain = find_mgmtdomain_by_ip(session, device0.management_ip)
        if mgmtdomain.id != find_mgmtdomain_by_ip(session, device1.management_ip).id:
            raise Exception("Uplink access devices have different mgmtdomains: {}, {}".format(
                device0.hostname, device1.hostname
            ))
    else:
        raise Exception("Unknown uplink device type")
    return mgmtdomain


def find_mgmtdomain_by_ip(session, ipv4_address: IPv4Address) -> Optional[Mgmtdomain]:
    mgmtdomains = session.query(Mgmtdomain).all()
    mgmtdom: Mgmtdomain
    for mgmtdom in mgmtdomains:
        mgmtdom_ipv4_network = IPv4Interface(mgmtdom.ipv4_gw).network
        if ipv4_address in mgmtdom_ipv4_network:
            return mgmtdom
    return None


def get_all_mgmtdomains(session, hostname: str) -> List[Mgmtdomain]:
    """
    Get all mgmtdomains for a specific distribution switch.

    Args:
        session: sqla session
        hostname: hostname of distribution switch

    Raises:
        ValueError: on invalid hostname etc
    """
    if not Device.valid_hostname(hostname):
        raise ValueError(f"Argument {hostname} is not a valid hostname")
    try:
        dev = session.query(Device).filter(Device.hostname == hostname).one()
    except NoResultFound:
        raise ValueError(f"hostname {hostname} not found in device database")

    mgmtdomains = session.query(Mgmtdomain). \
        filter((Mgmtdomain.device_a == dev) | (Mgmtdomain.device_b == dev)).all()
    return mgmtdomains


def json_dumper(obj):
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()