import enum
import re

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
    MLAG_PEER = 5
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

    @classmethod
    def interface_index_num(cls, ifname: str):
        """Calculate a unique numerical value for a physical interface name
        Ethernet1 -> 2
        Ethernet1/0 -> 201
        Ethernet4/3/2/1 -> 5040302

        Args:
            ifname: interface name, ex Ethernet1 or GigabitEthernet1/0/1

        Returns:
            int or none
        """
        index_num = 0
        # Match physical interface name and divide into "group" components
        match = re.match(r"^[a-zA-Z-]*([0-9]+\/?)([0-9]+\/?)?([0-9]+\/?)?([0-9]+\/?)?$", ifname)
        if not match:
            raise ValueError(f"Unable to parse interface name {ifname}")
        groups = match.groups()
        if not len(groups) == 4:
            raise ValueError(f"Unable to parse interface name {ifname}")
        # Ethernet4/3/2/1 don't miss any groups, Ethernet1 misses 3 groups etc
        missing_groups = 0
        for index, item in reversed(list(enumerate(groups, start=1))):
            if item:
                item_num = int(item.rstrip('/'))
                index_num += (100**(4-index-missing_groups)) * (item_num+1)
            else:
                missing_groups += 1
        return index_num

