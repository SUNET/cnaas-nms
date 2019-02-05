from sqlalchemy import Column, Integer, Unicode, String, UniqueConstraint, Enum
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from sqlalchemy_utils import IPAddressType

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
    serial = Column(String(64))
    ztp_mac = Column(String(12))
    platform = Column(String(64))
    state = Column(Enum(DeviceState))
    device_type = Column(Enum(DeviceType))
