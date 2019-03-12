from sqlalchemy import Column, Integer, Unicode, String, UniqueConstraint
from sqlalchemy import Enum, DateTime, Boolean
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from sqlalchemy_utils import IPAddressType
import ipaddress
import datetime
import enum
import re

import cnaas_nms.cmdb.base
import cnaas_nms.cmdb.site
from cnaas_nms.cmdb.linknet import Linknet

class DeviceException(Exception):
    pass

class DeviceStateException(DeviceException):
    pass

class DeviceState(enum.Enum):
    UNKNOWN = 0        # Unhandled programming error
    PRE_CONFIGURED = 1 # Pre-populated, not seen yet
    DHCP_BOOT = 2      # Something booted via DHCP, unknown device
    DISCOVERED = 3     # Something booted with base config, temp ssh access for conf push
    INIT = 4           # Moving to management VLAN, applying base template
    MANAGED = 5        # Correct managament and accessible via conf push
    MANAGED_NOIF = 6   # Only base system template managed, no interfaces?
    UNMANAGED = 99     # Device no longer maintained by conf push

    @classmethod
    def has_value(cls, value):
        return any(value == item.value for item in cls)

    @classmethod
    def has_name(cls, value):
        return any(value == item.name for item in cls)

class DeviceType(enum.Enum):
    UNKNOWN = 0
    ACCESS = 1
    DIST = 2
    CORE = 3

    @classmethod
    def has_value(cls, value):
        return any(value == item.value for item in cls)

    @classmethod
    def has_name(cls, value):
        return any(value == item.name for item in cls)

class Device(cnaas_nms.cmdb.base.Base):
    __tablename__ = 'device'
    __table_args__ = (
        None,
        UniqueConstraint('hostname'),
    )
    id = Column(Integer, autoincrement=True, primary_key=True)
    hostname = Column(String(64), nullable=False)
    site_id = Column(Integer, ForeignKey('site.id'))
    site = relationship("Site")
    description = Column(Unicode(255))
    management_ip = Column(IPAddressType)
    dhcp_ip = Column(IPAddressType)
    serial = Column(String(64))
    ztp_mac = Column(String(12))
    platform = Column(String(64))
    vendor = Column(String(64))
    model = Column(String(64))
    os_version = Column(String(64))
    synchronized = Column(Boolean, default=False)
    state = Column(Enum(DeviceState), nullable=False) # type: ignore
    device_type = Column(Enum(DeviceType), nullable=False)
    last_seen = Column(DateTime, default=datetime.datetime.now) # onupdate=now

    def as_dict(self):
        """Return JSON serializable dict."""
        d = {}
        for col in self.__table__.columns:
            value = getattr(self, col.name)
            if issubclass(value.__class__, enum.Enum):
                value = value.name
            elif issubclass(value.__class__, cnaas_nms.cmdb.base.Base):
                continue
            elif issubclass(value.__class__, ipaddress.IPv4Address):
                value = str(value)
            elif issubclass(value.__class__, datetime.datetime):
                value = str(value)
            d[col.name] = value
        return d

    def get_neighbors(self, session):
        """Look up neighbors from Linknets and return them as a list of Device objects."""
        linknets = self.get_linknets(session)
        ret = []
        for linknet in linknets:
            if linknet.device_a_id == self.id:
                ret.append(session.query(Device).filter(Device.id == linknet.device_b_id).one())
            else:
                ret.append(session.query(Device).filter(Device.id == linknet.device_a_id).one())
        return ret

    def get_linknets(self, session):
        """Look up linknets and return a list of Linknet objects."""
        ret = []
        linknets = session.query(Linknet).\
            filter(
                (Linknet.device_a_id == self.id)
                |
                (Linknet.device_b_id == self.id)
            )
        for linknet in linknets:
            ret.append(linknet)
        return ret

    @classmethod
    def valid_hostname(cls, hostname: str) -> bool:
        if hostname.endswith('.'):
            hostname = hostname[:-1]
        if len(hostname) < 1 or len(hostname) > 253:
            return False
        hostname_part_re = re.compile('^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$',
                                      re.IGNORECASE)
        return all(hostname_part_re.match(x) for x in hostname.split('.'))

