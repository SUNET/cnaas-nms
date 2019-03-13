from sqlalchemy import Column, Integer, Unicode, String, UniqueConstraint
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from sqlalchemy_utils import IPAddressType
import ipaddress
import datetime
import enum

import cnaas_nms.cmdb.base
import cnaas_nms.cmdb.site
import cnaas_nms.cmdb.device

class Mgmtdomain(cnaas_nms.cmdb.base.Base):
    __tablename__ = 'mgmtdomain'
    __table_args__ = (
        None,
        UniqueConstraint('device_a_id', 'device_b_id'),
    )
    id = Column(Integer, autoincrement=True, primary_key=True)
    ipv4_gw = Column(Unicode(18)) # 255.255.255.255/32
    device_a_id = Column(Integer, ForeignKey('device.id'))
    device_a = relationship("Device", foreign_keys=[device_a_id])
    device_a_ip = Column(IPAddressType)
    device_b_id = Column(Integer, ForeignKey('device.id'))
    device_b = relationship("Device", foreign_keys=[device_b_id])
    device_b_ip = Column(IPAddressType)
    site_id = Column(Integer, ForeignKey('site.id'))
    site = relationship("Site")
    vlan = Column(Integer)
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


