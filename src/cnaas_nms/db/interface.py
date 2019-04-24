import enum

from sqlalchemy import Column, Integer, Unicode
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql.json import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import Enum

import cnaas_nms.db.base
from cnaas_nms.db.device import Device


class InterfaceConfigType(enum.Enum):
    UNKNOWN = 0
    UNMANAGED = 1
    CONFIGFILE = 2
    CUSTOM = 3
    ACCESS_AUTO = 10
    ACCESS_UNTAGGED = 11
    ACCESS_TAGGED = 12

    @classmethod
    def has_value(cls, value):
        return any(value == item.value for item in cls)

    @classmethod
    def has_name(cls, value):
        return any(value == item.name for item in cls)


class Interface(cnaas_nms.db.base.Base):
    __tablename__ = 'interface'
    __table_args__ = (
        None,
    )
    device_id = Column(Integer, ForeignKey(Device.id), primary_key=True, index=True)
    device = relationship("Device", foreign_keys=[device_id])
    name = Column(Unicode(255), primary_key=True)
    configtype = Column(Enum(InterfaceConfigType), nullable=False)
    data = Column(JSONB)
