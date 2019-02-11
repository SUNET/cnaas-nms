from sqlalchemy import Column, Integer, Unicode, String, UniqueConstraint, Enum
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from sqlalchemy_utils import IPAddressType
import ipaddress

import enum

import cnaas_nms.cmdb.base
import cnaas_nms.cmdb.site

class DeviceState(enum.Enum):
    UNKNOWN = 0
    PRE_CONFIGURED = 1
    DISCOVERED = 2
    INIT = 3
    MANAGED = 4
    UNMANAGED = 5

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
            d[col.name] = value
        return d


