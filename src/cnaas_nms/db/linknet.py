import ipaddress
import enum
import datetime
from typing import Optional

from sqlalchemy import Column, Integer, Unicode, UniqueConstraint
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy_utils import IPAddressType

import cnaas_nms.db.base
import cnaas_nms.db.site
import cnaas_nms.db.device


class Linknet(cnaas_nms.db.base.Base):
    __tablename__ = 'linknet'
    __table_args__ = (
        None,
        UniqueConstraint('device_a_id', 'device_a_port'),
        UniqueConstraint('device_b_id', 'device_b_port'),
    )
    id = Column(Integer, autoincrement=True, primary_key=True)
    ipv4_network = Column(Unicode(18))
    device_a_id = Column(Integer, ForeignKey('device.id'))
    device_a = relationship("Device", foreign_keys=[device_a_id],
                            backref=backref("linknets_a", cascade="all, delete-orphan"))
    device_a_ip = Column(IPAddressType)
    device_a_port = Column(Unicode(64))
    device_b_id = Column(Integer, ForeignKey('device.id'))
    device_b = relationship("Device", foreign_keys=[device_b_id],
                            backref=backref("linknets_b", cascade="all, delete-orphan"))
    device_b_ip = Column(IPAddressType)
    device_b_port = Column(Unicode(64))
    site_id = Column(Integer, ForeignKey('site.id'))
    site = relationship("Site")
    description = Column(Unicode(255))

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
        return d

    @classmethod
    def create_linknet(cls, session, hostname_a: str, interface_a: str, hostname_b: str,
                       interface_b: str, ipv4_network: Optional[ipaddress.IPv4Network] = None,
                       strict_check: bool = True):
        """Add a linknet between two devices. If ipv4_network is specified both
        devices must be of type CORE or DIST."""
        dev_a: cnaas_nms.db.device.Device = session.query(cnaas_nms.db.device.Device).\
            filter(cnaas_nms.db.device.Device.hostname == hostname_a).one_or_none()
        if not dev_a:
            raise ValueError(f"Hostname {hostname_a} not found in database")
        if strict_check and ipv4_network and dev_a.device_type not in \
                [cnaas_nms.db.device.DeviceType.DIST, cnaas_nms.db.device.DeviceType.CORE]:
            raise ValueError(
                "Linknets can only be added between two core/dist devices " +
                "(hostname_a is {})".format(
                    str(dev_a.device_type)
                ))
        dev_b: cnaas_nms.db.device.Device = session.query(cnaas_nms.db.device.Device).\
            filter(cnaas_nms.db.device.Device.hostname == hostname_b).one_or_none()
        if not dev_b:
            raise ValueError(f"Hostname {hostname_b} not found in database")
        if strict_check and ipv4_network and dev_b.device_type not in \
                [cnaas_nms.db.device.DeviceType.DIST, cnaas_nms.db.device.DeviceType.CORE]:
            raise ValueError(
                "Linknets can only be added between two core/dist devices " +
                "(hostname_b is {})".format(
                    str(dev_b.device_type)
                ))

        new_linknet: Linknet = Linknet()
        new_linknet.device_a = dev_a
        new_linknet.device_a_port = interface_a
        new_linknet.device_b = dev_b
        new_linknet.device_b_port = interface_b
        if ipv4_network:
            if not isinstance(ipv4_network, ipaddress.IPv4Network) or ipv4_network.prefixlen != 31:
                raise ValueError("Linknet must be an IPv4Network with prefix length of 31")
            ip_a, ip_b = ipv4_network.hosts()
            new_linknet.device_a_ip = ip_a
            new_linknet.device_b_ip = ip_b
            new_linknet.ipv4_network = str(ipv4_network)
        dev_a.synchronized = False
        dev_b.synchronized = False
        return new_linknet
