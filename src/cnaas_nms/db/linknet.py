import datetime
import enum
import ipaddress
import itertools
from typing import List, Optional

from sqlalchemy import Column, ForeignKey, Integer, Unicode, UniqueConstraint
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utils import IPAddressType

import cnaas_nms.db.base
import cnaas_nms.db.device
import cnaas_nms.db.site


class Linknet(cnaas_nms.db.base.Base):
    __tablename__ = "linknet"
    __table_args__ = (
        None,
        UniqueConstraint("device_a_id", "device_a_port"),
        UniqueConstraint("device_b_id", "device_b_port"),
    )
    id = Column(Integer, autoincrement=True, primary_key=True)
    ipv4_network = Column(Unicode(18))
    ipv6_network = Column(Unicode(43))
    device_a_id = Column(Integer, ForeignKey("device.id"))
    device_a = relationship(
        "Device", foreign_keys=[device_a_id], backref=backref("linknets_a", cascade="all, delete-orphan")
    )
    device_a_ip = Column(IPAddressType)
    device_a_ipv6 = Column(IPAddressType)
    device_a_port = Column(Unicode(64))
    device_b_id = Column(Integer, ForeignKey("device.id"))
    device_b = relationship(
        "Device", foreign_keys=[device_b_id], backref=backref("linknets_b", cascade="all, delete-orphan")
    )
    device_b_ip = Column(IPAddressType)
    device_b_ipv6 = Column(IPAddressType)
    device_b_port = Column(Unicode(64))
    site_id = Column(Integer, ForeignKey("site.id"))
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

    def get_port(self, device_id):
        if device_id == self.device_a_id:
            return self.device_a_port
        if device_id == self.device_b_id:
            return self.device_b_port
        raise ValueError(f"The device_id {device_id} is not part of this linknet")

    def get_ip(self, device_id):
        if device_id == self.device_a_id:
            return self.device_a_ip
        if device_id == self.device_b_id:
            return self.device_b_ip
        raise ValueError(f"The device_id {device_id} is not part of this linknet")

    def get_ipv6(self, device_id):
        if device_id == self.device_a_id:
            return self.device_a_ipv6
        if device_id == self.device_b_id:
            return self.device_b_ipv6
        raise ValueError(f"The device_id {device_id} is not part of this linknet")

    def get_ipif(self, device_id):
        prefixlen = ipaddress.IPv4Network(self.ipv4_network).prefixlen
        if device_id == self.device_a_id:
            return f"{self.device_a_ip}/{prefixlen}"
        if device_id == self.device_b_id:
            return f"{self.device_b_ip}/{prefixlen}"
        raise ValueError(f"The device_id {device_id} is not part of this linknet")

    def get_ipifv6(self, device_id):
        if not self.ipv6_network:
            return  # we treat ipv6 as optional (for now)
        prefixlen = ipaddress.IPv6Network(self.ipv6_network).prefixlen
        if device_id == self.device_a_id:
            return f"{self.device_a_ip}/{prefixlen}"
        if device_id == self.device_b_id:
            return f"{self.device_b_ip}/{prefixlen}"
        raise ValueError(f"The device_id {device_id} is not part of this linknet")

    @staticmethod
    def deduplicate_linknet_dicts(linknets: List[dict]) -> List[dict]:
        """Take a list of dicts as returned from Device.get_linknets_as_dict
        and return a list of dicts without any duplicate entries based on
        hostname+port combinations."""
        populated_links = []
        ret = []
        for linknet in linknets:
            linknet_str_a = ":".join(
                [
                    linknet["device_a_hostname"],
                    linknet["device_a_port"],
                    linknet["device_b_hostname"],
                    linknet["device_b_port"],
                ]
            )
            linknet_str_b = ":".join(
                [
                    linknet["device_b_hostname"],
                    linknet["device_b_port"],
                    linknet["device_a_hostname"],
                    linknet["device_a_port"],
                ]
            )
            if linknet_str_a in populated_links or linknet_str_b in populated_links:
                continue
            populated_links.append(linknet_str_a)
            populated_links.append(linknet_str_b)
            ret.append(linknet)
        return ret

    @classmethod
    def create_linknet(
        cls,
        session,
        hostname_a: str,
        interface_a: str,
        hostname_b: str,
        interface_b: str,
        ipv4_network: Optional[ipaddress.IPv4Network] = None,
        ipv6_network: Optional[ipaddress.IPv6Network] = None,
        strict_check: bool = True,
    ):
        """Add a linknet between two devices. If ipv4_network/ipv6_network is specified both
        devices must be of type CORE or DIST."""
        dev_a: cnaas_nms.db.device.Device = (
            session.query(cnaas_nms.db.device.Device)
            .filter(cnaas_nms.db.device.Device.hostname == hostname_a)
            .one_or_none()
        )
        if not dev_a:
            raise ValueError(f"Hostname {hostname_a} not found in database")
        if (
            strict_check
            and (ipv4_network or ipv6_network)
            and dev_a.device_type not in [cnaas_nms.db.device.DeviceType.DIST, cnaas_nms.db.device.DeviceType.CORE]
        ):
            raise ValueError(
                "Linknets can only be added between two core/dist devices "
                + "(hostname_a is {})".format(str(dev_a.device_type))
            )
        dev_b: cnaas_nms.db.device.Device = (
            session.query(cnaas_nms.db.device.Device)
            .filter(cnaas_nms.db.device.Device.hostname == hostname_b)
            .one_or_none()
        )
        if not dev_b:
            raise ValueError(f"Hostname {hostname_b} not found in database")
        if (
            strict_check
            and (ipv4_network or ipv6_network)
            and dev_b.device_type not in [cnaas_nms.db.device.DeviceType.DIST, cnaas_nms.db.device.DeviceType.CORE]
        ):
            raise ValueError(
                "Linknets can only be added between two core/dist devices "
                + "(hostname_b is {})".format(str(dev_b.device_type))
            )

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
        if ipv6_network:
            if not isinstance(ipv6_network, ipaddress.IPv6Network):
                raise ValueError("IPv6 Linknet must be an IPv6Network")
            ip_a, ip_b = itertools.islice(ipv6_network.hosts(), 2)
            new_linknet.device_a_ipv6 = str(ip_a)
            new_linknet.device_b_ipv6 = str(ip_b)
            new_linknet.ipv6_network = str(ipv6_network)
        if strict_check:
            dev_a.synchronized = False
            dev_b.synchronized = False
        return new_linknet
