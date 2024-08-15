import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_utils import IPAddressType

import cnaas_nms.db.base
import cnaas_nms.db.device
from cnaas_nms.tools.log import get_logger

logger = get_logger()


class ReservedIP(cnaas_nms.db.base.Base):
    __tablename__ = "reservedip"
    __table_args__ = (None,)
    device_id: Mapped[int] = mapped_column(Integer, ForeignKey("device.id"), primary_key=True)
    ip_version: Mapped[int] = mapped_column(Integer, primary_key=True, default=4)
    device: Mapped["cnaas_nms.db.device.Device"] = relationship(
        back_populates="reserved_ips",
    )
    ip: Mapped[IPAddressType] = mapped_column(IPAddressType)
    last_seen: Mapped[DateTime] = mapped_column(DateTime, default=datetime.datetime.now)

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
    def clean_reservations(
        cls, session, device: Optional[cnaas_nms.db.device.Device] = None, expiry_time=datetime.timedelta(days=1)
    ):
        rip: Optional[ReservedIP] = None
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


cnaas_nms.db.device.Device.reserved_ips = relationship(
    ReservedIP, foreign_keys="ReservedIP.device_id", back_populates="device", cascade="all, delete-orphan"
)
