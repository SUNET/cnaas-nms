import datetime
import enum
import ipaddress
from ipaddress import IPv4Address, IPv4Interface
from typing import Optional

from sqlalchemy import Column, ForeignKey, Integer, String, Unicode, UniqueConstraint
from sqlalchemy.orm import load_only, relationship
from sqlalchemy_utils import IPAddressType

import cnaas_nms.db.base
import cnaas_nms.db.device
import cnaas_nms.db.site
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
        except Exception:  # noqa: S110
            pass
        return d

    def find_free_mgmt_ip(self, session) -> Optional[IPv4Address]:
        """Return first available IPv4 address from this Mgmtdomain's ipv4_gw network."""
        used_ips = []
        reserved_ips = []
        device_query = (
            session.query(Device).filter(Device.management_ip is not None).options(load_only("management_ip"))
        )
        for device in device_query:
            used_ips.append(device.management_ip)
        reserved_ip_query = session.query(ReservedIP).options(load_only("ip"))
        for reserved_ip in reserved_ip_query:
            reserved_ips.append(reserved_ip.ip)

        mgmt_net = IPv4Interface(self.ipv4_gw).network
        for num, host in enumerate(mgmt_net.hosts()):
            if num < 5:  # reserve 5 first hosts
                continue
            if host in reserved_ips:
                continue
            if host in used_ips:
                continue
            else:
                return IPv4Address(host)
        return None
