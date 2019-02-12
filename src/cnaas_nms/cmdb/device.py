from sqlalchemy import Column, Integer, Unicode, String, UniqueConstraint, Enum, DateTime
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from sqlalchemy_utils import IPAddressType
import ipaddress
import datetime
import enum

import cnaas_nms.cmdb.base
import cnaas_nms.cmdb.site

class DeviceState(enum.Enum):
    UNKNOWN = 0        # Unhandled programming error
    PRE_CONFIGURED = 1 # Pre-populated, not seen yet
    DHCP_BOOT = 2      # Something booted via DHCP, unknown device
    DISCOVERED = 3     # Something booted with base config, temp ssh access for conf push
    INIT = 4           # Moving to management VLAN, applying base template
    MANAGED = 5        # Correct managament and accessible via conf push
    MANAGED_NOIF = 6   # Only base system template managed, no interfaces?
    UNMANAGED = 99     # Device no longer maintained by conf push

class DeviceType(enum.Enum):
    UNKNOWN = 0
    ACCESS = 1
    DIST = 2
    CORE = 3

class Device(cnaas_nms.cmdb.base.Base):
    __tablename__ = 'device'
    __table_args__ = (
        None,
        UniqueConstraint('hostname', 'site_id'),
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
    state = Column(Enum(DeviceState))
    device_type = Column(Enum(DeviceType))
    last_seen = Column(DateTime, default=datetime.datetime.now)

    def as_dict(self):
        """Return JSON serializable dict."""
        d = {}
        for col in self.__table__.columns:
            value = getattr(self, col.name)
            if issubclass(value.__class__, enum.Enum):
                value = value.value
            elif issubclass(value.__class__, cnaas_nms.cmdb.base.Base):
                continue
            elif issubclass(value.__class__, ipaddress.IPv4Address):
                value = str(value)
            elif issubclass(value.__class__, datetime.datetime):
                value = str(value)
            d[col.name] = value
        return d


