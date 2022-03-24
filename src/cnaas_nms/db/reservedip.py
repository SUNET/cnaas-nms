import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utils import IPAddressType

import cnaas_nms.db.base
import cnaas_nms.db.device
from cnaas_nms.tools.log import get_logger

logger = get_logger()

time_delta = datetime.timedelta(days=1)


class ReservedIP(cnaas_nms.db.base.Base):
    __tablename__ = "reservedip"
    __table_args__ = (None,)
    device_id = Column(Integer, ForeignKey("device.id"), primary_key=True, index=True)
    device = relationship("Device", foreign_keys=[device_id], backref=backref("TempIP", cascade="all, delete-orphan"))
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

    @classmethod
    def clean_reservations(cls, session, device: Optional[cnaas_nms.db.device.Device] = None, expiry_time=time_delta):
        for rip in session.query(ReservedIP):
            if device and rip.device == device:
                logger.debug("Clearing reservation of ip {} for device {}".format(rip.ip, device.hostname))
                session.delete(rip)
            elif rip.last_seen < datetime.datetime.utcnow() - expiry_time:
                logger.debug(
                    "Clearing expired reservation of ip {} for device {} from {}".format(
                        rip.ip, rip.device.hostname, rip.last_seen
                    )
                )
                session.delete(rip)
