import ipaddress
import enum
import datetime

from sqlalchemy import Column, Integer, Unicode, UniqueConstraint
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy_utils import IPAddressType

import cnaas_nms.cmdb.base
import cnaas_nms.cmdb.site
import cnaas_nms.cmdb.device


class Linknet(cnaas_nms.cmdb.base.Base):
    __tablename__ = 'linknet'
    __table_args__ = (
        None,
        UniqueConstraint('device_a_id', 'device_a_port'),
        UniqueConstraint('device_b_id', 'device_b_port'),
    )
    id = Column(Integer, autoincrement=True, primary_key=True)
    ipv4_network = Column(Unicode(18))
    device_a_id = Column(Integer, ForeignKey('device.id'))
    device_a = relationship("Device", foreign_keys=[device_a_id])
    device_a_ip = Column(IPAddressType)
    device_a_port = Column(Unicode(64))
    device_b_id = Column(Integer, ForeignKey('device.id'))
    device_b = relationship("Device", foreign_keys=[device_b_id])
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
            elif issubclass(value.__class__, cnaas_nms.cmdb.base.Base):
                continue
            elif issubclass(value.__class__, ipaddress.IPv4Address):
                value = str(value)
            elif issubclass(value.__class__, datetime.datetime):
                value = str(value)
            d[col.name] = value
        return d


