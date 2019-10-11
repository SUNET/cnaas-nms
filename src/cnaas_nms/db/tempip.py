import datetime

from sqlalchemy import Column, Integer, DateTime
from sqlalchemy import ForeignKey
from sqlalchemy_utils import IPAddressType
from sqlalchemy.orm import relationship, backref

import cnaas_nms.db.base
import cnaas_nms.db.device


class TempIP(cnaas_nms.db.base.Base):
    __tablename__ = 'tempip'
    __table_args__ = (
        None,
    )
    device_id = Column(Integer, ForeignKey('device.id'), primary_key=True, index=True)
    device = relationship("Device", foreign_keys=[device_id],
                          backref=backref("TempIP", cascade="all, delete-orphan"))
    ip = Column(IPAddressType)
    last_seen = Column(DateTime, default=datetime.datetime.now)

    def as_dict(self) -> dict:
        """Return JSON serializable dict."""
        d = {}
        for col in self.__table__.columns:
            value = getattr(self, col.name)
            if issubclass(value.__class__, cnaas_nms.db.base.Base):
                continue
            d[col.name] = value
        return d
