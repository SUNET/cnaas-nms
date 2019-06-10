import enum

from sqlalchemy import Column, Integer, Unicode
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql.json import JSONB
from sqlalchemy.orm import relationship, backref
from sqlalchemy import Enum

import cnaas_nms.db.base
import cnaas_nms.db.device


class InterfaceConfigType(enum.Enum):
    UNKNOWN = 0
    UNMANAGED = 1
    CONFIGFILE = 2
    CUSTOM = 3
    TEMPLATE = 4
    ACCESS_AUTO = 10
    ACCESS_UNTAGGED = 11
    ACCESS_TAGGED = 12
    ACCESS_UPLINK = 13

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
    device_id = Column(Integer, ForeignKey('device.id'), primary_key=True, index=True)
    device = relationship("Device", foreign_keys=[device_id],
                          backref=backref("Interfaces", cascade="all, delete-orphan"))
    name = Column(Unicode(255), primary_key=True)
    configtype = Column(Enum(InterfaceConfigType), nullable=False)
    data = Column(JSONB)

    def as_dict(self) -> dict:
        """Return JSON serializable dict."""
        d = {}
        for col in self.__table__.columns:
            value = getattr(self, col.name)
            if issubclass(value.__class__, enum.Enum):
                value = value.name
            elif issubclass(value.__class__, cnaas_nms.db.base.Base):
                continue
            d[col.name] = value
        return d
