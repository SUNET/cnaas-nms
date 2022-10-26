import datetime
import enum
import ipaddress
from ipaddress import IPv4Address, IPv4Interface
from itertools import dropwhile, islice
from typing import Optional, Set

from sqlalchemy import Column, ForeignKey, Integer, String, Unicode, UniqueConstraint
from sqlalchemy.orm import load_only, relationship
from sqlalchemy_utils import IPAddressType

import cnaas_nms.db.base
import cnaas_nms.db.device
import cnaas_nms.db.site
from cnaas_nms.app_settings import api_settings
from cnaas_nms.db.device import Device
from cnaas_nms.db.reservedip import ReservedIP


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

    def find_free_mgmt_ip(self, session) -> Optional[IPv4Address]:
        """Return first available IPv4 address from this Mgmtdomain's ipv4_gw network."""
        taken_ips = self._get_taken_ips(session)

        def is_taken(addr):
            return addr in taken_ips

        mgmt_net = IPv4Interface(self.ipv4_gw).network
        candidates = islice(mgmt_net.hosts(), api_settings.MGMTDOMAIN_RESERVED_COUNT, None)
        free_ips = dropwhile(is_taken, candidates)
        return next(free_ips, None)

    @staticmethod
    def _get_taken_ips(session) -> Set[IPv4Address]:
        """Returns the full set of taken (used + reserved) IP addresses"""
        device_query = (
            session.query(Device).filter(Device.management_ip is not None).options(load_only("management_ip"))
        )
        used_ips = set(device.management_ip for device in device_query)
        reserved_ip_query = session.query(ReservedIP).options(load_only("ip"))
        reserved_ips = set(reserved_ip.ip for reserved_ip in reserved_ip_query)

        return used_ips | reserved_ips
