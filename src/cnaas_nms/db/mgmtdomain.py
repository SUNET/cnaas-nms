import datetime
import enum
import ipaddress
from ipaddress import IPv4Address, IPv6Address, ip_interface
from itertools import dropwhile, islice
from typing import Optional, Set, Union

from sqlalchemy import Column, ForeignKey, Integer, String, Unicode, UniqueConstraint
from sqlalchemy.orm import load_only, relationship
from sqlalchemy_utils import IPAddressType

import cnaas_nms.db.base
import cnaas_nms.db.device
import cnaas_nms.db.site
from cnaas_nms.app_settings import api_settings
from cnaas_nms.db.device import Device
from cnaas_nms.db.reservedip import ReservedIP

IPAddress = Union[IPv4Address, IPv6Address]


class Mgmtdomain(cnaas_nms.db.base.Base):
    __tablename__ = "mgmtdomain"
    __table_args__ = (
        None,
        UniqueConstraint("device_a_id", "device_b_id"),
    )
    id = Column(Integer, autoincrement=True, primary_key=True)
    ipv4_gw = Column(Unicode(18))  # 255.255.255.255/32
    ipv6_gw = Column(Unicode(43))  # fe80:0000:0000:0000:0000:0000:0000:0000/128
    device_a_id = Column(Integer, ForeignKey("device.id"))
    device_a = relationship("Device", foreign_keys=[device_a_id])
    device_a_ip = Column(IPAddressType)
    device_b_id = Column(Integer, ForeignKey("device.id"))
    device_b = relationship("Device", foreign_keys=[device_b_id])
    device_b_ip = Column(IPAddressType)
    site_id = Column(Integer, ForeignKey("site.id"))
    site = relationship("Site")
    vlan = Column(Integer)
    description = Column(Unicode(255))
    esi_mac = Column(String(12))

    def as_dict(self):
        """Return JSON serializable dict."""
        d = {}
        for col in self.__table__.columns:
            value = getattr(self, col.name)
            if issubclass(value.__class__, enum.Enum):
                value = value.value
            elif issubclass(value.__class__, cnaas_nms.db.base.Base):
                continue
            elif issubclass(value.__class__, ipaddress.IPv4Address):
                value = str(value)
            elif issubclass(value.__class__, datetime.datetime):
                value = str(value)
            d[col.name] = value
        try:
            d["device_a"] = str(self.device_a.hostname)
            d["device_b"] = str(self.device_b.hostname)
        except Exception:
            pass
        return d

    @property
    def is_dual_stack(self) -> bool:
        """Returns True if this mgmt domain is dual-stack"""
        return bool(self.ipv4_gw) and bool(self.ipv6_gw)

    @property
    def primary_gw(self) -> Optional[str]:
        """Returns the primary gateway interface for this Mgmtdomain, depending on the configured preference"""
        primary_version = api_settings.MGMTDOMAIN_PRIMARY_IP_VERSION
        return self.ipv4_gw if primary_version == 4 else self.ipv6_gw

    @property
    def secondary_gw(self) -> Optional[str]:
        """Returns the secondary gateway interface for this Mgmtdomain, depending on the configured preference"""
        primary_version = api_settings.MGMTDOMAIN_PRIMARY_IP_VERSION
        return self.ipv6_gw if primary_version == 4 else self.ipv4_gw

    def find_free_primary_mgmt_ip(self, session) -> Optional[IPAddress]:
        """Returns the first available IP address from this Mgmtdomain's primary network.

        The return value type depends on what IP version CNaaS-NMS is configured to use for
        primary management addresses.
        """
        primary_version = api_settings.MGMTDOMAIN_PRIMARY_IP_VERSION
        return self.find_free_mgmt_ip(session, version=primary_version)

    def find_free_secondary_mgmt_ip(self, session) -> Optional[IPAddress]:
        """Returns the first available IP address from this Mgmtdomain's secondary network (if
        such a network is configured).

        The return value type depends on what IP version CNaaS-NMS is configured to use for
        primary management addresses.
        """
        secondary_version = 6 if api_settings.MGMTDOMAIN_PRIMARY_IP_VERSION == 4 else 4
        return self.find_free_mgmt_ip(session, version=secondary_version)

    def find_free_mgmt_ip(self, session, version: int = 4) -> Optional[IPAddress]:
        """Returns the first available IP address from this Mgmtdomain's network.

        Defaults to returning an IPv4 address from ipv4_gw. Set version=6 to get an address from
        the equivalent IPv6 network of ipv6_gw.
        """
        taken_ips = self._get_taken_ips(session)

        def is_taken(addr):
            return addr in taken_ips

        if version not in (4, 6):
            raise ValueError("version must be 4 or 6")
        intf_addr = self.ipv4_gw if version == 4 else self.ipv6_gw
        if intf_addr is None:
            return None  # can't find an addr if no subnet is defined
        else:
            mgmt_net = ip_interface(intf_addr).network
        candidates = islice(mgmt_net.hosts(), api_settings.MGMTDOMAIN_RESERVED_COUNT, None)
        free_ips = dropwhile(is_taken, candidates)
        return next(free_ips, None)

    @staticmethod
    def _get_taken_ips(session) -> Set[IPAddress]:
        """Returns the full set of taken (used + reserved) IP addresses"""
        device_query = (
            session.query(Device).filter(Device.management_ip is not None).options(load_only("management_ip"))
        )
        used_ips = set(device.management_ip for device in device_query)
        reserved_ip_query = session.query(ReservedIP).options(load_only("ip"))
        reserved_ips = set(reserved_ip.ip for reserved_ip in reserved_ip_query)

        return used_ips | reserved_ips
